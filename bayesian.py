import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from sklearn.metrics import accuracy_score, mean_squared_error
from sklearn.preprocessing import KBinsDiscretizer
from copy import copy
import numpy as np
import networkx as nx

from pgmpy.estimators import HillClimbSearch
from pgmpy.estimators import BDeuScore, K2Score, BicScore
from pgmpy.models import BayesianModel
from pgmpy.sampling import BayesianModelSampling
from pgmpy.inference import VariableElimination
from pgmpy.base import DAG


def draw_comparative_hist(parametr: str, original_data: pd.DataFrame, data_sampled: pd.DataFrame):
    final_df = pd.DataFrame()
    df1 = pd.DataFrame()
    df1[parametr] = original_data[parametr]
    df1['Data'] = 'Original data'
    df1['Probability'] = df1[parametr].apply(
        lambda x: (df1.groupby(parametr)[parametr].count()[x]) / original_data.shape[0])
    df2 = pd.DataFrame()
    df2[parametr] = data_sampled[parametr]
    df2['Data'] = 'Synthetic data'
    df2['Probability'] = df2[parametr].apply(
        lambda x: (df2.groupby(parametr)[parametr].count()[x]) / data_sampled.shape[0])
    final_df = pd.concat([df1, df2])
    sns.barplot(x=parametr, y="Probability", hue="Data", data=final_df)
    plt.show()


def accuracy_params_restoration(bn: BayesianModel, data: pd.DataFrame):
    bn.fit(data)
    result = pd.DataFrame(columns=['Parameter', 'accuracy', 'mse', 'mae'])
    bn_infer = VariableElimination(bn)
    for j, param in enumerate(data.columns):
        accuracy = 0
        test_param = data[param]
        test_data = data.drop(columns=param)
        evidence = test_data.to_dict('records')
        predicted_param = []
        for element in evidence:
            prediction = bn_infer.map_query(variables=[param], evidence=element)
            predicted_param.append(prediction[param])
        accuracy = accuracy_score(test_param.values, predicted_param)
        mae = sum(np.array(predicted_param) - test_param.values) / len(predicted_param)
        mse = mean_squared_error(predicted_param, test_param.values)
        result.loc[j, 'mae'] = mae
        result.loc[j, 'mse'] = mse
        result.loc[j, 'Parameter'] = param
        result.loc[j, 'accuracy'] = accuracy
    return result


def sampling(bn: DAG, data: pd.DataFrame, n):
    G = nx.DiGraph()
    G.add_edges_from(bn.edges())
    pos = nx.layout.circular_layout(G)
    nx.draw(G, pos, with_labels=True, font_weight='bold')
    plt.show()

    accuracy = accuracy_params_restoration(BayesianModel(bn.edges()), data)
    print(accuracy)

    bn_new = BayesianModel(bn.edges())
    bn_new.fit(data)
    sampler = BayesianModelSampling(bn_new)
    sample = sampler.forward_sample(size=n, return_type='dataframe')
    return sample, accuracy


if __name__ == "__main__":
    data = pd.read_csv("data/data_spb.csv", usecols=['STATION', 'SLP', 'DEWP', 'MAX',
                                                     'MIN', 'TEMP', 'WDSP'], index_col=0)
    data = data.loc[26063099999]
    # TEMP - Mean temperature (.1 Fahrenheit)
    # SLP - Mean sea level pressure for the day in millibars to tenths. Missing = 9999.9 (.1 mb)
    # WDSP – Mean wind speed (.1 knots)

    # удаление пропущенных значений
    data.reset_index(inplace=True, drop=True)
    data.dropna(inplace=True)
    missing_vals = data.loc[data.SLP == 9999.9]
    data = data.replace(9999.9, np.nan, regex=True)
    data.dropna(inplace=True)
    print(missing_vals)
    print(len(data))

    # Корреляционная матрица
    corr = data.corr()
    mask = np.zeros_like(corr, dtype=np.bool)
    mask[np.triu_indices_from(mask)] = True
    sns.heatmap(corr, annot=True, fmt='.1f', cmap='Blues')
    plt.show()

    data = data[1:2000]
    data2 = data[['DEWP', 'SLP', 'TEMP', 'WDSP']]
    missing_vals = missing_vals[1:2000]

    bins = 4
    transformed_data = copy(data)
    transformed_data2 = copy(data2)

    est = KBinsDiscretizer(n_bins=bins, encode='ordinal', strategy='kmeans')
    data_discrete = est.fit_transform(transformed_data.values[:, 0:6])
    transformed_data[['DEWP', 'MAX', 'MIN', 'SLP', 'TEMP', 'WDSP']] = data_discrete
    hc_BicScore = HillClimbSearch(transformed_data, scoring_method=K2Score(transformed_data))
    best_model_BicScore = hc_BicScore.estimate()

    sample_Bic, accuracy1 = sampling(best_model_BicScore, transformed_data, len(data))
    sample_Bic[['DEWP', 'MAX', 'MIN', 'SLP',  'TEMP', 'WDSP']] = est.inverse_transform(sample_Bic[
               ['DEWP', 'MAX', 'MIN', 'SLP',  'TEMP', 'WDSP']].values)

    draw_comparative_hist('DEWP', transformed_data, sample_Bic)
    draw_comparative_hist('SLP', transformed_data, sample_Bic)
    draw_comparative_hist('TEMP', transformed_data, sample_Bic)
    draw_comparative_hist('WDSP', transformed_data, sample_Bic)

    # ручное
    # est2 = KBinsDiscretizer(n_bins=bins, encode='ordinal', strategy='kmeans')
    # data_discrete2 = est2.fit_transform(data2.values[:, 0:4])
    # transformed_data2[['DEWP', 'SLP', 'TEMP', 'WDSP']] = data_discrete2
    # hc_BicScore2 = HillClimbSearch(transformed_data2, scoring_method=K2Score(transformed_data2))
    # best_model_BicScore2 = hc_BicScore2.estimate()
    #
    # sample_Bic2, accuracy2 = sampling(best_model_BicScore2, transformed_data2, len(data2))
    # sample_Bic2[['DEWP', 'SLP', 'TEMP', 'WDSP']] = est2.inverse_transform(sample_Bic2[
    #             ['DEWP', 'SLP', 'TEMP', 'WDSP']].values)
    #
    # draw_comparative_hist('DEWP', transformed_data2, sample_Bic2)
    # draw_comparative_hist('SLP', transformed_data2, sample_Bic2)
    # draw_comparative_hist('TEMP', transformed_data2, sample_Bic2)
    # draw_comparative_hist('WDSP', transformed_data2, sample_Bic2)

    # sns.distplot(data['WDSP'], label='Original data')
    # sns.distplot(sample_Bic['WDSP'], label='Generated data')
    # sns.distplot(sample_Bic2['WDSP'], label='Generated data dist')
    # plt.legend()
    # plt.show()
    #
    # sns.distplot(data['TEMP'], label='Original data')
    # sns.distplot(sample_Bic['TEMP'], label='Generated data')
    # sns.distplot(sample_Bic2['TEMP'], label='Generated data dist')
    # plt.legend()
    # plt.show()
    #
    # sns.distplot(data['SLP'], label='Original data')
    # sns.distplot(sample_Bic['SLP'], label='Generated data')
    # sns.distplot(sample_Bic2['SLP'], label='Generated data dist')
    # plt.legend()
    # plt.show()
    #
    # sns.distplot(data['DEWP'], label='Original data')
    # sns.distplot(sample_Bic['DEWP'], label='Generated data')
    # sns.distplot(sample_Bic2['DEWP'], label='Generated data dist')
    # plt.legend()
    # plt.show()
    #
    # print(accuracy1, accuracy2)


    predicted_param = []
    bm = BayesianModel(best_model_BicScore.edges())
    bm.fit(transformed_data)
    ve = VariableElimination(bm)
    for param in enumerate(missing_vals['SLP']):
        missing_vals = missing_vals.drop(columns='SLP')
        evidence = missing_vals.to_dict('records')
        for element in evidence:
            prediction = ve.map_query(variables=[param], evidence=element)
            predicted_param.append(prediction)
    missing_vals['SLP'] = predicted_param
    predicted_param = est.inverse_transform(predicted_param)

    data['SLP'].plot(color='navy', label='Реальные значения')
    missing_vals['SLP'].plot(color='gold', label='Заполненные значения')

    plt.legend()
    plt.show()

