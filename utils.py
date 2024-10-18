import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import base64
import hashlib
import hmac
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import pandas as pd
import requests
from datetime import datetime
import matplotlib.pyplot as plt



date_of_data = datetime.now().strftime('%Y%m%d')
base_url = "https://ui.boondmanager.com/api"
contacts_url = f"{base_url}/contacts"


USER_TOKEN = "3134372e73696a6f"
CLIENT_TOKEN = "73696a6f"
CLIENT_KEY = "b058463851b9a6a7fcc7"

def base64_url_encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

def build_jwt_client():
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "userToken": USER_TOKEN,
        "clientToken": CLIENT_TOKEN,
        "time": int(time.time()),
        "mode": "normal"
    }

    header_encoded = base64_url_encode(json.dumps(header).encode('utf-8'))
    payload_encoded = base64_url_encode(json.dumps(payload).encode('utf-8'))

    signing_input = f"{header_encoded}.{payload_encoded}"
    signature = hmac.new(
        CLIENT_KEY.encode('utf-8'),
        signing_input.encode('utf-8'),
        hashlib.sha256
    ).digest()

    signature_encoded = base64_url_encode(signature)
    jwt_token = f"{signing_input}.{signature_encoded}"
    return jwt_token

def fetch_page(url ,jwt_token, page, per_page=30):
    headers = {
        "X-Jwt-Client-Boondmanager": jwt_token,
        "Content-Type": "application/json"
    }
    params = {'page': page, 'limit': per_page}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to retrieve page {page}. Status code: {response.status_code}")
            return None
    except requests.RequestException as e:
        print(f"Error fetching page {page}: {e}")
        return None

def fetch_all_pages_in_parallel(url, jwt_token, total_pages, per_page=30):
    all_data = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_page, url, jwt_token, page, per_page): page for page in range(1, total_pages + 1)}
        for future in as_completed(futures):
            page_data = future.result()
            if page_data is not None:
                all_data.append(page_data)
    return all_data

def process_contacts_data(managers, manager_state_count, all_contacts_data):
    for page_data in all_contacts_data:
        for contact in page_data['data']:
            manager_id = contact['relationships']['mainManager']['data']['id']
            if manager_id in managers:
                manager_name = managers.get(manager_id, "No manager found")
                contact_state = contact['attributes']['state']
                
                if contact_state == 1:
                    manager_state_count[manager_name]["p"] += 1
                elif contact_state == 3:
                    manager_state_count[manager_name]["pq"] += 1
                elif contact_state == 2:
                    manager_state_count[manager_name]["cl"] += 1
                elif contact_state == 7:
                    manager_state_count[manager_name]["pdo"] += 1

    dataframe_bm = pd.DataFrame([
        {"Prénom": manager, "Prospect": counts["p"], "Prospect Qualifié": counts["pq"], "Client": counts["cl"], "Pas donneur d'ordre": counts["pdo"]}
        for manager, counts in manager_state_count.items()
    ])
    return dataframe_bm

def save_all_data_to_json(prefixe_file, all_data):
    try:
        with open(f"{prefixe_file}_{date_of_data}.json", "w") as f:
            json.dump(all_data, f, indent=4)
        print(f"All contacts data saved to contacts_all_data_{date_of_data}.json")
    except Exception as e:
        print(f"Error saving contacts to JSON: {e}")

def save_to_csv(df, current_date):

    data_dir = "C:/Users/sijo-user/OneDrive - SIJO/automatisationMailing/"
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    csv_file = f"{data_dir}/table-{current_date}.csv"
    if os.path.exists(csv_file):
        df.to_csv(csv_file, mode='w', index=False)
    else:
        df.to_csv(csv_file, index=False)
    print(f"Données sauvegardées dans un ./{data_dir}/table-{current_date}.csv.")

def send_email(subject, body):
    
    sender_email = "anir@sijo.fr"
    receiver_email = "mickael@sijo.fr"
    password = "CANADA123azert@!"

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))

    try:
        server = smtplib.SMTP('smtp.office365.com', 587)
        server.starttls()
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        print("Email envoyé!")
        server.quit()
    except Exception as e:
        print(f"Failed to send email. Error: {e}")

def delta_df_now(df_actual):
    repertoire = "C:/Users/sijo-user/OneDrive - SIJO/automatisationMailing/"
    fichiers = [os.path.join(repertoire, f) for f in os.listdir(repertoire) if os.path.isfile(os.path.join(repertoire, f))]
    fichiers_trie = sorted(fichiers, key=os.path.getctime, reverse=True)
    dernier_fichier = fichiers_trie[0] if fichiers_trie else None

    if dernier_fichier:
        df_ancien = pd.read_csv(dernier_fichier)
    else:
        raise FileNotFoundError("Aucun fichier trouvé dans le répertoire.")

    df_merged = pd.merge(df_actual, df_ancien, on='Prénom', suffixes=('_nouveau', '_ancien'))

    df_delta = pd.DataFrame()
    df_delta['Prénom'] = df_merged['Prénom']
    df_delta['Prospect'] = df_merged['Prospect_nouveau'] - df_merged['Prospect_ancien']
    df_delta['Prospect Qualifié'] = df_merged['Prospect Qualifié_nouveau'] - df_merged['Prospect Qualifié_ancien']
    df_delta['Client'] = df_merged['Client_nouveau'] - df_merged['Client_ancien']
    df_delta["Pas donneur d'ordre"] = df_merged["Pas donneur d'ordre_nouveau"] - df_merged["Pas donneur d'ordre_ancien"]

    save_to_csv(df_actual, date_of_data)

    return df_delta

def evolution():
    try:
        repertoire = "C:/Users/sijo-user/OneDrive - SIJO/automatisationMailing/"
        fichiers = [os.path.join(repertoire, f) for f in os.listdir(repertoire) if os.path.isfile(os.path.join(repertoire, f))]
        fichiers_trie = sorted(fichiers, key=os.path.getctime, reverse=True)

        person_data = {}

        for fichier in fichiers_trie:
            aaaammdd = fichier.split("/")[-1].replace(".csv","").split("-")[-1]
            year = aaaammdd[0:4]
            month = aaaammdd[4:6]
            day = aaaammdd[6:8]
            
            date = f"{day}/{month}/{year}"

            df = pd.read_csv(fichier)

            for index, row in df.iterrows():
                person = row['Prénom']
                nb_prospect = row['Prospect']
                nb_client = row['Client']
                nb_prospect_qualifie = row['Prospect Qualifié']
                
                if person not in person_data:
                    person_data[person] = {'date': [], 'Prospect': [], 'Client': [], 'Prospect Qualifié': []}
                
                person_data[person]['date'].append(date)
                person_data[person]['Prospect'].append(nb_prospect)
                person_data[person]['Client'].append(nb_client)
                person_data[person]['Prospect Qualifié'].append(nb_prospect_qualifie)
        
        plt.figure(figsize=(10, 6))
        for person, data in person_data.items():
            plt.plot(data['date'], data['Prospect Qualifié'], label=f"{person} (Prospect Qualifié)")
        
        plt.xlabel('Date DD/MM/AAAA')
        plt.ylabel('Nombre Prospect Qualifié')
        plt.title('Nombre Prospect Qualifié par BM')
        plt.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()

        plot_qualifie_filename = "prospect_qualifie.png"

        plt.savefig(plot_qualifie_filename)
        plt.close()

        plt.figure(figsize=(10, 6))
        for person, data in person_data.items():
            if person == "Mickael":
                continue
            plt.plot(data['date'], data['Prospect'], label=f"{person} (Prospect)")
        
        plt.xlabel('Date DD/MM/AAAA')
        plt.ylabel('Nombre Prospect')
        plt.title('Nombre Prospect par BM')
        plt.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()

        plot_prospect_filename = "prospect.png"

        plt.savefig(plot_prospect_filename)
        plt.close()

        plt.figure(figsize=(10, 6))
        for person, data in person_data.items():
            plt.plot(data['date'], data['Client'], label=f"{person} (Client)")
        
        plt.xlabel('Date DD/MM/AAAA')
        plt.ylabel('Nombre Client')
        plt.title('Nombre Client par BM')
        plt.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()

        plot_client_filename = "client.png"

        plt.savefig(plot_client_filename)
        plt.close()
        
    except Exception as e:
        print(f"An error has occured! {e}")
        return False
    return True
    
def create_html_table(total_df, delta_df=pd.DataFrame()):
    table_total = total_df.to_html(index=False, classes="styled-table")
    table_delta = delta_df.to_html(index=False, classes="styled-table")

    style = """
    <style>
        .styled-table {
            font-family: Arial, sans-serif;
            border-collapse: collapse;
            width: 100%;
        }
        .styled-table thead tr {
            background-color: #009879;
            color: #ffffff;
            text-align: left;
        }
        .styled-table th, .styled-table td {
            padding: 12px 15px;
            border: 1px solid #dddddd;
        }
        .styled-table tbody tr:nth-child(even) {
            background-color: #f3f3f3;
        }
        .styled-table tbody tr:hover {
            background-color: #f1f1f1;
        }
    </style>
    """

    def img_to_base64(img_path):
        with open(img_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode("utf-8")

    prospect_qualifie_base64 = img_to_base64("prospect_qualifie.png")
    prospect_base64 = img_to_base64("prospect.png")
    client_base64 = img_to_base64("client.png")

    image_html = f"""
    <h2>Graphiques:</h2>
    <p><b>Nombre Prospect Qualifié par BM:</b></p>
    <img src="data:image/png;base64,{prospect_qualifie_base64}" alt="Prospect Qualifié" style="width:600px;height:400px;">
    <p><b>Nombre Prospect par BM:</b></p>
    <img src="data:image/png;base64,{prospect_base64}" alt="Prospect" style="width:600px;height:400px;">
    <p><b>Nombre Client par BM:</b></p>
    <img src="data:image/png;base64,{client_base64}" alt="Client" style="width:600px;height:400px;">
    """

    subject = f"Rapport {date_of_data[6:8]}/{date_of_data[4:6]}/{date_of_data[0:4]} : Contacts Business Manager"
    body = f"""
    <p>Bonjour,</p>
    <p>Voici le rapport du {date_of_data[6:8]}/{date_of_data[4:6]}/{date_of_data[0:4]} du nombre de contacts par Business Manager:</p>
    <p><b>Ceci est le delta des données entre la semaine dernière et cette semaine:</b></p>
    """ + style + table_delta + """
    <p><b>Ceci est le total des données sur BoondManager:</b></p>
    """ + style + table_total + """
    <p><br></p>
    """ + image_html

    # os.remove("prospect_qualifie.png")
    # os.remove("prospect.png")
    # os.remove("client.png")
    
    return subject, body
