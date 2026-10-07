"""Curvas de ajustes DI1: dados B3 arquivados pelo projeto PYield."""
import io
from pathlib import Path
import numpy as np
import pandas as pd
import requests
import streamlit as st

URL = 'https://github.com/crdcj/pyield-data/releases/latest/download/b3_futures.parquet'
MESES = dict(zip('FGHJKMNQUVXZ', range(1, 13)))

def preparar_historico(bruto, feriados):
    di = bruto.loc[bruto.TckrSymb.str.match(r'^DI1[FGHJKMNQUVXZ]\d{2}$'), ['TradDt', 'TckrSymb', 'AdjstdQtTax']].copy()
    calendario = np.busdaycalendar(holidays=np.array(feriados, dtype='datetime64[D]'))
    contratos = di.TckrSymb.unique()
    vencimentos = {}
    for codigo in contratos:
        primeiro = f'{2000 + int(codigo[-2:]):04d}-{MESES[codigo[3]]:02d}-01'
        vencimentos[codigo] = np.busday_offset(np.datetime64(primeiro), 0, roll='forward', busdaycal=calendario)
    datas = pd.to_datetime(di.TradDt).to_numpy(dtype='datetime64[D]')
    finais = np.array([vencimentos[c] for c in di.TckrSymb], dtype='datetime64[D]')
    di['dias_uteis'] = np.busday_count(datas, finais, busdaycal=calendario)
    di['data'] = pd.to_datetime(di.TradDt)
    di['taxa'] = pd.to_numeric(di.AdjstdQtTax, errors='coerce')
    di = di.loc[(di.dias_uteis > 0) & np.isfinite(di.taxa) & (di.taxa > -100)]
    return di[['data', 'dias_uteis', 'taxa']].drop_duplicates(['data', 'dias_uteis']).sort_values(['data', 'dias_uteis'])

@st.cache_data(ttl=43200, show_spinner=False)
def carregar_historico():
    pasta = Path(__file__).parent / 'data'
    salvo = pd.read_csv(pasta / 'historico_di1.csv.gz', sep=';', parse_dates=['data'])
    try:
        resposta = requests.get(URL, timeout=40)
        resposta.raise_for_status()
        feriados = pd.read_csv(pasta / 'feriados_di.txt', comment='#', header=None)[0]
        feriados = pd.to_datetime(feriados, format='%d/%m/%Y').to_numpy(dtype='datetime64[D]')
        novo = preparar_historico(pd.read_parquet(io.BytesIO(resposta.content)), feriados)
        if not novo.empty:
            salvo = pd.concat([salvo, novo]).drop_duplicates(['data', 'dias_uteis'], keep='last')
        aviso = None
    except (requests.RequestException, ValueError, OSError, ImportError):
        aviso = 'Download do histórico indisponível. Exibindo a cópia incluída no projeto.'
    return salvo, aviso
