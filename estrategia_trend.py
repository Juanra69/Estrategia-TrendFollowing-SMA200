import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import pandas as pd
import yfinance as yf

# 1. Definición de parámetros para S&P 500 y Nasdaq 100
CONFIG = {
    'S&P 500': {'ticker': '^GSPC', 'banda': 0.01},  # +/- 1%
    'Nasdaq 100': {'ticker': '^NDX', 'banda': 0.015},  # +/- 1.5%
}


def analizar_indice(nombre, ticker, banda):
  # Descargar histórico (1 año y medio para calcular bien la MM200)
  df = yf.download(ticker, period='2y', progress=False)['Close']
  if isinstance(df, pd.DataFrame):
    df = df.squeeze()

  data = pd.DataFrame({'Close': df})
  data['MM200'] = data['Close'].rolling(window=200).mean()
  data['Banda_Superior'] = data['MM200'] * (1 + banda)
  data['Banda_Inferior'] = data['MM200'] * (1 - banda)

  # Detectar cruces de las bandas
  # Cruce al alza de la banda superior
  data['Cruce_Alza_Banda'] = (data['Close'] > data['Banda_Superior']) & (
      data['Close'].shift(1) <= data['Banda_Superior'].shift(1)
  )

  # Cruce a la baja de la banda inferior
  data['Cruce_Baja_Banda'] = (data['Close'] < data['Banda_Inferior']) & (
      data['Close'].shift(1) >= data['Banda_Inferior'].shift(1)
  )

  data['Estado_Alcista'] = data['Close'] > data['Banda_Superior']
  data['Estado_Bajista'] = data['Close'] < data['Banda_Inferior']

  ultima = data.iloc[-1]
  anterior = data.iloc[-2]

  return {
      'nombre': nombre,
      'precio': ultima['Close'],
      'mm200': ultima['MM200'],
      'banda_sup': ultima['Banda_Superior'],
      'banda_inf': ultima['Banda_Inferior'],
      'cruce_alza': ultima['Cruce_Alza_Banda'],
      'cruce_baja': ultima['Cruce_Baja_Banda'],
      'estado_actual': (
          'ALCISTA (Risk-On)'
          if ultima['Close'] > ultima['Banda_Superior']
          else (
              'REFUGIO (Risk-Off)'
              if ultima['Close'] < ultima['Banda_Inferior']
              else 'EN BANDA NEUTRA'
          )
      ),
  }


def enviar_correo(asunto, cuerpo):
  remitente = os.environ['EMAIL_SENDER']
  password = os.environ['EMAIL_PASSWORD']
  destinatario = os.environ['EMAIL_RECEIVER']

  msg = MIMEMultipart()
  msg['From'] = remitente
  msg['To'] = destinatario
  msg['Subject'] = asunto
  msg.attach(MIMEText(cuerpo, 'plain'))

  try:
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(remitente, password)
    server.sendmail(remitente, destinatario, msg.as_string())
    server.quit()
    print('Correo de alerta enviado correctamente.')
  except Exception as e:
    print(f'Error al enviar correo: {e}')


# 2. Evaluación diaria
alertas = []

for nombre, cfg in CONFIG.items():
  res = analizar_indice(nombre, cfg['ticker'], cfg['banda'])

  if res['cruce_alza']:
    alertas.append(
        f"🚨 [COMPRA ETF 2x - {res['nombre']}]\n"
        f"El índice ha cruzado AL ALZA la Banda Superior (+{CONFIG[nombre]['banda']*100}% de MM200).\n"
        f"- Precio Cierre: {res['precio']:.2f}\n"
        f"- MM200: {res['mm200']:.2f}\n"
        f"- Banda Sup: {res['banda_sup']:.2f}\n"
        f"👉 Acción: Rotar capital desde monetario/bonos hacia ETF Apalancado 2x."
    )
  elif res['cruce_baja']:
    alertas.append(
        f"⚠️ [VENTA / ROTACIÓN A MONETARIO - {res['nombre']}]\n"
        f"El índice ha cruzado A LA BAJA la Banda Inferior (-{CONFIG[nombre]['banda']*100}% de MM200).\n"
        f"- Precio Cierre: {res['precio']:.2f}\n"
        f"- MM200: {res['mm200']:.2f}\n"
        f"- Banda Inf: {res['banda_inf']:.2f}\n"
        f"👉 Acción: Salir de ETF 2x y rotar hacia Bonos ultracortos / Monetarios."
    )

if alertas:
  asunto = '🚨 [ALERTA TREND FOLLOWING] Cambio de estado en Índices'
  cuerpo = '\n\n----------------------------------------\n\n'.join(alertas)
  enviar_correo(asunto, cuerpo)
else:
  print('Sin cambios de estado/cruces en las bandas envolventes hoy.')
   
