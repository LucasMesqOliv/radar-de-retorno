# Radar de Retorno

Aplicação em Streamlit para analisar retornos acumulados e anualizados, janelas móveis e comparações entre índices de mercado.

## Executar localmente

```powershell
streamlit run app.py
```

A senha do aplicativo deve ser definida no arquivo local `.streamlit/secrets.toml` ou nas configurações de secrets da hospedagem:

```toml
APP_PASSWORD = "sua-senha"
```

O arquivo local de secrets não é enviado ao repositório.

## Base de dados local

O aplicativo usa `data/radar_retorno.db`, uma base SQLite compacta com CDI,
IPCA, S&P 500 e as cotas dos fundos já consultados. O site lê essa base antes
de acessar as fontes externas e grava apenas os registros novos.

Para reconstruir a base inicial com os dados oficiais e incorporar os caches
de fundos existentes:

```powershell
python scripts/preparar_base.py
```

Fontes: SGS/BCB, Yahoo Finance (`^GSPC`) e informes diários da CVM.
