"""Consulta de curvas DI x Pré da B3 e comparação de datas."""
import base64
from datetime import date, datetime, timedelta, timezone
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

BASE = 'https://sistemaswebb3-derivativos.b3.com.br/referenceRatesProxy/Search/'
FONTE = 'https://sistemaswebb3-derivativos.b3.com.br/referenceRatesPage/all?language=pt-br'

def consultar(endpoint, **campos):
    payload = dict(language='pt-br', id='PRE', **campos)
    token = base64.b64encode(json.dumps(payload).encode()).decode()
    resposta = requests.get(BASE + endpoint + '/' + token, timeout=30,
        headers={'Referer': FONTE, 'Origin': 'https://sistemaswebb3-derivativos.b3.com.br'})
    resposta.raise_for_status()
    return resposta

@st.cache_data(ttl=3600, show_spinner=False)
def datas_b3():
    return sorted({date.fromisoformat(x[:10]) for x in consultar('GetDate').json()})

def ler_csv(conteudo):
    try:
        texto = conteudo.decode('utf-8-sig')
    except UnicodeDecodeError:
        texto = conteudo.decode('latin-1')
    df = pd.read_csv(io.StringIO(texto), sep=';')
    df = df.rename(columns={'Dias Úteis': 'dias_uteis', 'Preço/Taxa': 'taxa', 'Data': 'data'})
    if not {'dias_uteis', 'taxa'}.issubset(df.columns):
        raise ValueError('O CSV precisa das colunas dias_uteis e taxa (ou Dias Úteis e Preço/Taxa).')
    if 'Descrição da Taxa' in df:
        df = df[df['Descrição da Taxa'].str.casefold().eq('di x pré')].copy()
    for coluna in ['dias_uteis', 'taxa']:
        df[coluna] = pd.to_numeric(df[coluna].astype(str).str.replace(',', '.', regex=False), errors='raise')
    if df.empty or df[['dias_uteis', 'taxa']].isna().any().any() or not np.isfinite(df[['dias_uteis', 'taxa']]).all().all():
        raise ValueError('A curva está vazia ou contém valores inválidos.')
    if (df.dias_uteis <= 0).any() or (df.taxa <= -100).any():
        raise ValueError('Prazo deve ser positivo e taxa deve ser maior que -100%.')
    return df

@st.cache_data(ttl=3600, show_spinner=False)
def baixar_curva(data_iso):
    texto = consultar('GetDownloadFile', date=data_iso).text.strip().strip('"')
    if not texto:
        raise ValueError('Arquivo indisponível para esta data na B3.')
    df = ler_csv(base64.b64decode(texto, validate=True))
    return df[['dias_uteis', 'taxa']].drop_duplicates('dias_uteis').sort_values('dias_uteis')

def interpolar(df, prazo):
    """Interpolação linear no log do fator acumulado, sem extrapolar."""
    if prazo < df.dias_uteis.min() or prazo > df.dias_uteis.max():
        return np.nan
    fatores = np.log1p(df.taxa.to_numpy() / 100) * df.dias_uteis.to_numpy() / 252
    return float(np.expm1(np.interp(prazo, df.dias_uteis, fatores) * 252 / prazo) * 100)

def pagina_curva_di():
    st.title('Curva de juros DI')
    st.write('Compare a curva DI × Pré em diferentes datas e acompanhe a abertura ou o fechamento dos juros por prazo.')
    st.caption('Taxas anuais em % • base de 252 dias úteis • curva referencial da B3 derivada dos futuros DI, sem cotações intradiárias.')
    hoje = datetime.now(timezone(timedelta(hours=-3))).date()
    pasta = Path(__file__).parent / 'data' / 'curvas_di'
    curvas = {}
    if pasta.exists():
        for arquivo in pasta.glob('*.csv'):
            try:
                curvas[date.fromisoformat(arquivo.stem)] = ler_csv(arquivo.read_bytes())[['dias_uteis', 'taxa']].sort_values('dias_uteis')
            except (ValueError, OSError):
                st.warning(f'Não foi possível ler a curva salva {arquivo.name}.')
    with st.expander('Importar histórico de curvas'):
        st.write('CSV com data (AAAA-MM-DD), dias_uteis e taxa (% a.a.), separado por ponto e vírgula. Pode conter várias datas. Para um arquivo original da B3, informe a data abaixo.')
        data_importacao = st.date_input('Data do arquivo B3', value=hoje, max_value=hoje)
        arquivos = st.file_uploader('Arquivos CSV', type='csv', accept_multiple_files=True)
        if st.button('Salvar histórico', disabled=not arquivos):
            try:
                novos = {}
                for arquivo in arquivos:
                    df = ler_csv(arquivo.getvalue())
                    if 'data' in df:
                        df['data'] = pd.to_datetime(df.data, format='%Y-%m-%d', errors='raise').dt.date
                        if (df.data > hoje).any():
                            raise ValueError('O arquivo contém datas futuras.')
                        grupos = df.groupby('data')
                    else:
                        grupos = [(data_importacao, df)]
                    for dia, grupo in grupos:
                        novos[dia] = grupo[['dias_uteis', 'taxa']].drop_duplicates('dias_uteis').sort_values('dias_uteis')
                pasta.mkdir(parents=True, exist_ok=True)
                for dia, df in novos.items():
                    df.to_csv(pasta / f'{dia.isoformat()}.csv', sep=';', index=False)
                curvas.update(novos)
                st.success(f'{len(novos)} curvas importadas.')
            except (ValueError, OSError) as erro:
                st.error(str(erro))
    try:
        disponiveis = [d for d in datas_b3() if d <= hoje]
    except (requests.RequestException, ValueError) as erro:
        disponiveis = []
        st.warning('B3 indisponível no momento. As curvas salvas continuam acessíveis.')
    datas = sorted(set(disponiveis) | set(curvas))
    if not datas:
        st.info('Nenhuma curva disponível. Tente novamente ou importe o histórico.')
        return
    referencia = st.date_input('Data de referência', value=datas[-1], max_value=hoje)
    periodos = st.multiselect('Comparar com', [1, 3, 6, 12, 24], default=[1, 6, 12], format_func=lambda m: f'{m} meses atrás')
    personalizadas = st.multiselect('Adicionar datas disponíveis', datas, format_func=lambda d: d.strftime('%d/%m/%Y'))
    pedidos = [('Referência', referencia)] + [(f'{m}m atrás', (pd.Timestamp(referencia) - pd.DateOffset(months=m)).date()) for m in periodos] + [('Personalizada', d) for d in personalizadas]
    selecionadas = {}
    for rotulo, alvo in pedidos:
        anteriores = [d for d in datas if d <= alvo and (alvo - d).days <= 7]
        if not anteriores:
            st.warning(f'{rotulo}: não há curva próxima de {alvo:%d/%m/%Y}. Importe o histórico para comparar esse período.')
            continue
        dia = max(anteriores)
        if dia not in curvas:
            try:
                with st.spinner(f'Consultando B3 — {dia:%d/%m/%Y}'):
                    curvas[dia] = baixar_curva(dia.isoformat())
                try:
                    pasta.mkdir(parents=True, exist_ok=True)
                    curvas[dia].to_csv(pasta / f'{dia.isoformat()}.csv', sep=';', index=False)
                except OSError:
                    st.warning('Não foi possível guardar esta curva em disco.')
            except (requests.RequestException, ValueError) as erro:
                st.warning(f'{dia:%d/%m/%Y}: curva indisponível. {erro}')
                continue
        selecionadas[dia] = curvas[dia]
        if dia != alvo:
            st.caption(f'{rotulo}: solicitado {alvo:%d/%m/%Y}; pregão utilizado {dia:%d/%m/%Y}.')
    if not selecionadas:
        return
    limite = st.select_slider('Prazo máximo no gráfico', options=[1, 2, 5, 10, 20, 30, 40], value=10, format_func=lambda x: f'{x} anos')
    fig = go.Figure()
    for dia, df in sorted(selecionadas.items(), reverse=True):
        recorte = df[df.dias_uteis <= limite * 252]
        fig.add_trace(go.Scatter(x=recorte.dias_uteis / 252, y=recorte.taxa, mode='lines', name=dia.strftime('%d/%m/%Y'), hovertemplate='%{x:.2f} anos<br>%{y:.2f}% a.a.<extra>%{fullData.name}</extra>'))
    fig.update_layout(template='plotly_white', height=500, xaxis_title='Prazo (anos de 252 dias úteis)', yaxis_title='Taxa (% a.a.)', hovermode='x unified', legend=dict(orientation='h', y=1.12))
    st.plotly_chart(fig, use_container_width=True)
    prazos = [21, 63, 126, 252, 504, 756, 1260, 2520]
    tabela = pd.DataFrame({dia.strftime('%d/%m/%Y'): [interpolar(df, p) for p in prazos] for dia, df in sorted(selecionadas.items(), reverse=True)}, index=['1m', '3m', '6m', '1 ano', '2 anos', '3 anos', '5 anos', '10 anos'])
    st.subheader('Taxas por prazo (% a.a.)')
    st.dataframe(tabela.style.format('{:.2f}', na_rep='—'), use_container_width=True)
    st.caption('Prazos padronizados interpolados no log do fator acumulado. Não há extrapolação além dos pontos disponíveis.')
    if len(tabela.columns) > 1:
        atual = tabela.columns[0]
        variacoes = tabela.iloc[:, 1:].apply(lambda c: (tabela[atual] - c) * 100)
        variacoes.columns = [f'{atual} vs {c}' for c in variacoes.columns]
        st.subheader('Variação da curva (pontos-base)')
        st.caption('Positivo: juros subiram. Negativo: juros caíram. 100 pontos-base = 1 ponto percentual.')
        st.plotly_chart(go.Figure([go.Bar(x=variacoes.index, y=variacoes[c], name=c) for c in variacoes]).update_layout(template='plotly_white', barmode='group', yaxis_title='Pontos-base'), use_container_width=True)
    exportacao = pd.concat([df.assign(data=dia.isoformat()) for dia, df in selecionadas.items()], ignore_index=True)
    st.download_button('Baixar curvas em CSV', exportacao[['data', 'dias_uteis', 'taxa']].to_csv(sep=';', index=False).encode('utf-8-sig'), 'curvas_di.csv', 'text/csv')
    st.markdown(f'[Fonte: taxas referenciais B3]({FONTE})')
