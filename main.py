from utils import build_jwt_client, fetch_all_pages_in_parallel, fetch_page, process_contacts_data, create_html_table, send_email, delta_df_now, evolution
import math
import time


def main():
    base_url = "https://ui.boondmanager.com/api"
    contacts_url = f"{base_url}/contacts"
    resources_url = f"{base_url}/resources"

    try:
        jwt_token_client = build_jwt_client()

        first_page_contacts_data = fetch_page(contacts_url, jwt_token_client, page=1)
        first_page_resources_data = fetch_page(resources_url, jwt_token_client, page=1)

        if first_page_contacts_data and first_page_resources_data:
            total_rows_contacts = first_page_contacts_data.get('meta', {}).get('totals', {}).get('rows', 0)
            total_rows_resources = first_page_resources_data.get('meta', {}).get('totals', {}).get('rows', 0)
            per_page = 30
            total_pages_contacts = math.ceil(total_rows_contacts / per_page)
            total_pages_resources = math.ceil(total_rows_resources / per_page)

            all_contacts_data = fetch_all_pages_in_parallel(contacts_url, jwt_token_client, total_pages_contacts, per_page)
            all_resources_data = fetch_all_pages_in_parallel(resources_url, jwt_token_client, total_pages_resources, per_page)
            
            if all_resources_data and all_contacts_data:
                managers = {}
                manager_state_count = {}
                for res_page in all_resources_data:
                    res_data = res_page["data"]
                    for res in res_data:
                        if res["attributes"]["typeOf"] == 2 and res["attributes"]["state"] == 1:
                            managers[res["id"]] = res["attributes"]["firstName"]
                for manager in managers:
                    manager_state_count[managers[manager]] = {"p": 0, "pq": 0, "cl": 0, "pdo": 0}

                table_DF = process_contacts_data(managers, manager_state_count, all_contacts_data)
                print("Evolution")
                
                print("Delta")
                DF_delta = delta_df_now(table_DF)
                time.sleep(5)
                evolution()
                subject, body = create_html_table(table_DF, DF_delta)
                send_email(subject, body)
    except Exception as e:
        print(f"An error has occurred:\n {e}")

if __name__ == "__main__":
    main()
