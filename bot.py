from flask import Flask, jsonify
import pyodbc
import requests
import time
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

# Configurações do banco de dados SQL Server
DB_CONFIG = {
    "driver": "{ODBC Driver 17 for SQL Server}",
    "server": "agiluscred.dyndns.org,11000",
    "database": "dbMe7",
    "username": "dashbme7",
    "password": "marcelo_me7"
}

# Novo URL do webhook do Discord
DISCORD_WEBHOOK_URL = 'https://discord.com/api/webhooks/1317092880019619940/8w4brG5pnO_i8UAH6q23ay8mOYIPc9Y4VkT5AMX7-TRp4lBeaJ3gxUyDI0PJ7r_3Ck8A'

# Variáveis para armazenar o último CPF e data da venda enviada
last_sale_cpf = None
last_sale_date = None

# Caminho do template de imagem
TEMPLATE_PATH = "template.png"

# Caminho da fonte
FONT_PATH = "Anton.ttf"

# Função para conectar ao banco de dados
def get_database_connection():
    connection_string = (
        f"DRIVER={DB_CONFIG['driver']};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
        f"UID={DB_CONFIG['username']};"
        f"PWD={DB_CONFIG['password']}"
    )
    return pyodbc.connect(connection_string, timeout=10)

# Função para gerar imagem personalizada
def generate_sale_image(sale_data):
    try:
        image = Image.open(TEMPLATE_PATH)  # Use o caminho correto do seu template
        draw = ImageDraw.Draw(image)

        # Configurar fontes
        try:
            font_body = ImageFont.truetype(FONT_PATH, 30)
        except IOError:
            print("Erro ao carregar a fonte, utilizando a fonte padrão.")
            font_body = ImageFont.load_default()

        # Mensagens a serem exibidas
        texts = [
            f"Vendedor: {sale_data['agente']}",
            f"Cliente: {sale_data['nome']} (CPF: {sale_data['cpf']})",
            f"Valor da Venda: R$ {sale_data['valor_bruto']:.2f}"
        ]

        # Calcular a largura e altura total dos textos
        total_height = 0
        text_widths = []
        for text in texts:
            text_bbox = draw.textbbox((0, 0), text, font=font_body)  # Substituto de textsize
            text_width = text_bbox[2] - text_bbox[0]  # Largura do texto
            text_widths.append(text_width)
            total_height += text_bbox[3] - text_bbox[1] + 10  # Altura do texto + margem

        # Calcular posição inicial para centralizar os textos
        image_width, image_height = image.size
        current_y = (image_height - total_height) // 2  # Centralizar verticalmente

        for i, text in enumerate(texts):
            text_width = text_widths[i]
            x = (image_width - text_width) // 2  # Centralizar horizontalmente
            draw.text((x, current_y), text, fill="#bf0404", font=font_body)  # Cor #bf0404
            text_bbox = draw.textbbox((x, current_y), text, font=font_body)
            current_y += text_bbox[3] - text_bbox[1] + 10  # Avançar para a próxima linha

        # Salvar imagem gerada
        output_path = "sale_notification.png"
        image.save(output_path)
        return output_path
    except Exception as e:
        print(f"Erro ao gerar a imagem: {e}")
        return None

# Função para enviar notificação ao Discord
def send_discord_notification(sale_data):
    image_path = generate_sale_image(sale_data)

    if image_path is None:
        print("Erro ao gerar a imagem, não será enviada ao Discord.")
        return

    try:
        with open(image_path, "rb") as img:
            # Enviar imagem com texto
            response = requests.post(
                DISCORD_WEBHOOK_URL,
                files={"file": img}
            )

        if response.status_code == 204:
            print("Notificação enviada ao Discord com sucesso!")
        else:
            print(f"Erro ao enviar notificação: {response.text}")
    except Exception as e:
        print(f"Erro ao enviar notificação ao Discord: {e}")

# Função para verificar o banco de dados
def check_new_sales():
    global last_sale_cpf, last_sale_date
    conn = get_database_connection()
    cursor = conn.cursor()

    query = """
        SELECT TOP 1 agente, valor_bruto, nome, cpf, data
        FROM vw_vendas
        WHERE fase = 'INCLUSAO SEM CONFERENCIA'
        ORDER BY data DESC
    """
    cursor.execute(query)
    sale = cursor.fetchone()

    if sale:
        sale_data = {
            "agente": sale[0],
            "valor_bruto": sale[1],
            "nome": sale[2],
            "cpf": sale[3],
            "data": sale[4]
        }

        if (sale_data["cpf"] != last_sale_cpf) or (sale_data["data"] != last_sale_date):
            send_discord_notification(sale_data)
            last_sale_cpf = sale_data["cpf"]
            last_sale_date = sale_data["data"]

    cursor.close()
    conn.close()

# Loop contínuo para monitoramento
if __name__ == '__main__':
    print("Iniciando o monitoramento de vendas...")
    while True:
        try:
            check_new_sales()
        except pyodbc.Error as err:
            print(f"Erro ao conectar ao banco de dados: {err}")
            print("Tentando reconectar em 10 segundos...")
            time.sleep(10)
        time.sleep(60)
