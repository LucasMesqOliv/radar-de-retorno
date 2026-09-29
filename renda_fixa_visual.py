"""Escala compartilhada entre o mapa na tela e o relatório de renda fixa."""

ESCALA_CARREGO = [
    (0.0, "#e9a5a5"),
    (0.25, "#f8dddd"),
    (0.5, "#f4f6f8"),
    (0.75, "#bae5cf"),
    (1.0, "#65bf99"),
]


def comparar_com_carrego(valores, linha_carrego):
    """Valores e diferenças em p.p.; intensidade de cor normalizada por prazo."""
    referencia = valores[linha_carrego]
    diferencas = [
        [0.0 if abs(valor - base) < 1e-9 else valor - base
         for valor, base in zip(linha, referencia)]
        for linha in valores
    ]
    limites = [max(abs(linha[j]) for linha in diferencas) or 1.0
               for j in range(len(referencia))]
    intensidade = [[valor / limites[j] for j, valor in enumerate(linha)]
                   for linha in diferencas]
    return diferencas, intensidade


def cor_carrego(intensidade):
    """Interpola a mesma escala divergente do Plotly para as células do PDF."""
    posicao = (max(-1.0, min(1.0, intensidade)) + 1) / 2
    for (inicio, cor_a), (fim, cor_b) in zip(ESCALA_CARREGO, ESCALA_CARREGO[1:]):
        if posicao <= fim:
            peso = (posicao - inicio) / (fim - inicio)
            canais = [round(int(cor_a[i:i + 2], 16) * (1 - peso)
                            + int(cor_b[i:i + 2], 16) * peso)
                      for i in (1, 3, 5)]
            return "#" + "".join(f"{canal:02x}" for canal in canais)
    return ESCALA_CARREGO[-1][1]
