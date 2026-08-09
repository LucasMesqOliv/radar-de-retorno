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

## Base de dados permanente

O aplicativo também aceita PostgreSQL. Quando a chave `DATABASE_URL` está
configurada nos secrets do Streamlit, os índices e fundos novos são gravados
no banco online e sobrevivem às reinicializações do site. Sem essa chave, o
SQLite local continua sendo usado automaticamente.

Exemplo de configuração:

```toml
DATABASE_URL = "postgresql://usuario:senha@servidor:5432/banco?sslmode=require"
```

Depois de configurar a conexão, copie os dados atuais do SQLite para o banco
permanente executando:

```powershell
python scripts/migrar_para_postgres.py
```

Para atualizar no banco permanente o cadastro de fundos e classes da CVM:

```powershell
python scripts/precarregar_cadastro_fundos.py
```

O site consulta o cadastro permanente por nome, CNPJ, administrador ou gestor,
retornando somente os resultados da pesquisa. O cadastro oficial é renovado
periodicamente; o histórico de cotas continua sendo carregado sob demanda.

O endereço do banco é uma credencial e nunca deve ser salvo no GitHub.
