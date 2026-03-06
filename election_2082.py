import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import os

import concurrent.futures

## Tuple of constituency
constituency_tuple = (
    "achham1", "achham2", "arghakhanchi1", "illam1", "illam2", "udayaur1",
    "udayaur2", "okhaldhunga1", "kanchanpur1", "kanchanpur2", "kanchanpur3",
    "kapilbstu1", "kapilbstu2", "kapilbstu3", "kathmandu1", "kathmandu10",
    "kathmandu2", "kathmandu3", "kathmandu4", "kathmandu5", "kathmandu6",
    "kathmandu7", "kathmandu8", "kathmandu9", "kabrepalanchok1", "kabrepalanchok2",
    "kalikot1", "kaski1", "kaski2", "kaski3", "kailali1", "kailali2", "kailali3",
    "kailali4", "kailali5", "khotang1", "gulmi1", "gulmi2", "gorkha1", "gorkha2",
    "chitwan1", "chitwan2", "chitwan3", "jajarkot1", "jumla1", "jhapa1", "jhapa2",
    "jhapa3", "jhapa4", "jhapa5", "dadeldhura1", "doti1", "dolpa1", "tanahu1",
    "tanahu2", "taplejung", "terathum1", "dang1", "dang2", "dang3", "darchula1",
    "dailekh1", "dailekh2", "dolkha1", "dhankuta1", "dhanusa1", "dhanusa2",
    "dhanusa3", "dhanusa4", "dhading1", "dhading2", "parasi1", "parasi2",
    "nawalpur1", "nawalpur2", "nuwakot1", "nuwakot2", "parbat1", "parsa1",
    "parsa2", "parsa3", "parsa4", "panchthar1", "palpa1", "palpa2", "pyuthan1",
    "bajhang1", "bardiya1", "bardiya2", "banke1", "banke2", "banke3", "baglung1",
    "baglung2", "bajura1", "bara1", "bara2", "bara3", "bara4", "baitadi1",
    "bhaktapur1", "bhaktapur2", "bhojpur1", "makwanpur1", "makwanpur2", "manang1",
    "mahottari1", "mahottari2", "mahottari3", "mahottari4", "mugu1", "mustang1",
    "morang1", "morang2", "morang3", "morang4", "morang5", "morang6", "myagdi1",
    "rasuwa1", "ramechap1", "rukum2", "rukum1", "rupendehi1", "rupendehi2",
    "rupendehi3", "rupendehi4", "rupendehi5", "rolpa1", "rautahat1", "rautahat2",
    "rautahat3", "rautahat4", "lamjung1", "lalitpur1", "lalitpur2", "lalitpur3",
    "sankhuwasabha1", "saptari1", "saptari2", "saptari3", "saptari4", "sarlahi1",
    "sarlahi2", "sarlahi3", "sarlahi4", "salyan1", "sindhupalchowk1",
    "sindhupalchowk2", "sindhuli1", "sindhuli2", "siraha1", "siraha2",
    "siraha3", "siraha4", "sunsari1", "sunsari2", "sunsari3", "sunsari4",
    "surkhet1", "surkhet2", "solukhumbu1", "syangja1", "syangja2", "humla1"
)

#-------------- Convert Roman digit into Nepali digits -----------
# Create table once outside
NEPALI_TABLE = str.maketrans("0123456789", "०१२३४५६७८९")
def to_nepali(number):
    # Convert the input to string and translate
    return str(number).translate(NEPALI_TABLE)

## Voter data
def election_2082_get_voter_data(constituency):
    url = f"https://election.onlinekhabar.com/central-chetra/{constituency}"
    headers = {'User-Agent': 'Mozilla/5.0'}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # 1. Total Votes
        total_votes_tag = soup.find('p', class_='text-[1.5rem]')
        if total_votes_tag:
            raw_val = total_votes_tag.get_text(strip=True).replace(',', '')
            # Python int() handles Nepali digits automatically once commas are gone
            clean_total_votes = int(raw_val)
        else:
            clean_total_votes = 0

        # 2. Vote Percentage
        voted_tag = soup.find('span', string=lambda t: t and "Percent Voted" in t)
        if voted_tag:
            percent_text = voted_tag.find_next_sibling('span').get_text(strip=True)
            clean_percent = float(percent_text.replace('%', ''))
        else:
            clean_percent = 0.0

        # 3. Calculate Total Casted Votes
        total_casted_votes = int(clean_total_votes * (clean_percent / 100))

        return {
            "Constituency": constituency,
            "Total Votes": clean_total_votes,
            "Vote %": clean_percent,
            "Total Casted Votes": total_casted_votes
        }

    except Exception as e:
        print(f"Error scraping {constituency}: {e}")
        return {
            "Constituency": constituency,
            "Total Votes": 0,
            "Vote %": 0.0,
            "Total Casted Votes": 0
        }

def get_all_voter_data():
    """
    loop through all constituencies and scrape vote data
    :return:
    """
    results_list = []
    print(f"Starting scrape for {len(constituency_tuple)} constituencies...")

    for i, con in enumerate(constituency_tuple, 1):
        print(f"[{i}/{len(constituency_tuple)}] Fetching data for: {con}")
        data = election_2082_get_voter_data(con)
        print(data)

        results_list.append(data)

        # Small delay to be polite to the server
        time.sleep(0.5)

    # Create DataFrame
    df = pd.DataFrame(results_list)

    # Save to CSV
    filename = "election_2082_voter_stats.csv"
    df.to_csv(filename, index=False, encoding='utf-8-sig')

    print(f"\nDone! Data saved to {filename}")
    print(df.head())  # Preview the first few rows

## political parties data
def get_party_list():
    url = "https://election.onlinekhabar.com/parties"
    headers = {'User-Agent': 'Mozilla/5.0'}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        party_data_list = []

        # Target the main grid container
        container = soup.find('div', class_='okel-party-lists')

        if container:
            # Find all party cards within the container
            party_cards = container.find_all('div', class_='okel-candidate-card')

            for card in party_cards:
                # 1. Get Party Name
                # Targeting the specific link with the class 'line-clamp-1' inside the square div
                name_tag = card.find('div', class_='candidate-card-square').find('a', class_='line-clamp-1')
                party_name = name_tag.get_text(strip=True) if name_tag else "N/A"

                # 2. Get Logo URL (checking for 'src')
                img_tag = card.find('div', class_='candidate-image-holder').find('img') if card.find('div', class_='candidate-image-holder') else None
                logo_url = img_tag.get('src') if img_tag else "N/A"

                party_data_list.append({
                    "Party Name": party_name,
                    "Logo URL": logo_url
                })

                print(f"Party Name: {party_name}. Logo URL: {logo_url}")

        # Only save if we actually found parties
        if party_data_list:
            # Convert list of dictionaries to a DataFrame
            df = pd.DataFrame(party_data_list)
            # Use 'utf-8-sig' so Nepali characters display correctly in Excel
            filename = "election_2082_party_list.csv"
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"\nDone! Party list saved to {filename}")
        else:
            print("No party data found to save.")

        return party_data_list

    except Exception as e:
        print(f"Error scraping parties: {e}")
        return []

# Vote counting update
def update_election_count(constituency):
    url = f"https://election.onlinekhabar.com/central-chetra/{constituency}"
    headers = {'User-Agent': 'Mozilla/5.0'}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # 1. Get Constituency Display Name (e.g., कपिलवस्तु - ३)
        display_name = "N/A"
        header_tag = soup.find('h2', class_='okel-section-title')
        if header_tag:
            header_text = header_tag.get_text(strip=True)
            if '[' in header_text and ']' in header_text:
                display_name = header_text.split('[')[-1].split(']')[0].strip()

        # 2. Process Candidate Table
        candidates = []
        list_wrapper = soup.find('div', id='PratakshyaList')

        if list_wrapper:
            table_body = list_wrapper.find('tbody')
            if table_body:
                for row in table_body.find_all('tr'):
                    # Using .find() safely for each column
                    name_tag = row.find('span', class_='line-clamp-1')
                    party_tag = row.find('span', class_='text-[14px]')
                    vote_tag = row.find('span', class_='text-[1.15rem]')
                    # Sex and Age
                    details_tag = row.find('span', class_='opacity-60')

                    # Check if counting has not started yet
                    status = "Counting Ongoing" # Default
                    # Check if counting has not started yet
                    if row.find('div', class_='okel-not-started'):
                        status = "Not Started"
                    else:
                        status_tag = row.find('span', class_='okel-flag')
                        if status_tag:
                            status_text = status_tag.get_text(strip=True)
                            if "अग्रता" in status_text:
                                status = "Leading"
                            elif "विजयी" in status_text:
                                status = "Winner"

                    # Only append if we at least found a name
                    if name_tag:
                        # Extract and split Sex/Age text
                        details_text = details_tag.get_text(strip=True) if details_tag else "N/A, N/A"
                        # Split by comma: "पुरुष, ४३ वर्ष" -> ["पुरुष", " ४३ वर्ष"]
                        details_split = details_text.split(',')
                        sex = details_split[0].strip() if len(details_split) > 0 else "N/A"
                        age = details_split[1].strip() if len(details_split) > 1 else "N/A"

                        candidates.append({
                            "ID": constituency,
                            "Constituency": display_name,
                            "name": name_tag.get_text(strip=True),
                            "party": party_tag.get_text(strip=True) if party_tag else "Independent",
                            "votes": vote_tag.get_text(strip=True) if vote_tag else "0",
                            "sex": sex,
                            "age": age,
                            "Status": status   # Added Status
                        })

        # # --- PRINT RESULTS ---
        # print(f"{'VOTES':<10} | {'NAME':<20} | {'SEX':<8} | {'AGE':<10} | {'PARTY'}")
        # print("-" * 75)
        # for c in candidates:
        #     print(f"{c['votes']:<10} | {c['name']:<20} | {c['sex']:<8} | {c['age']:<10} | {c['party']}")

        # --- Terminal Print Logic ---
        print(f"\nconstituency: {constituency} | {display_name}")
        print(f"{'VOTES':<10} | {'NAME':<20} | {'SEX':<8} | {'AGE':<10} | {'STATUS':<12} | {'PARTY'}")
        print("-" * 90)
        for c in candidates:
            # Note: 'Status' is added to the print to show Leading/Winner/Not Started
            print(
                f"{c['votes']:<10} | {c['name']:<20} | {c['sex']:<8} | {c['age']:<10} | {c['Status']:<12} | {c['party']}")
        print("-" * 90)

        return candidates

    except Exception as e:
        print(f"\n[!] Error fetching {constituency}: {e}")
        return []  # Ensure we return an empty list, not None


def get_all_live_results(st_progress=None, st_status=None):
    """
    Scrapes all constituencies using 5 parallel threads and saves
    the final result in a single batch for maximum performance.
    """
    filename = "live_election_results_2082.csv"
    backup_filename = "live_election_results_2082_backup.csv"

    # 1. Handle Backups (Keep previous data safe)
    if os.path.exists(filename):
        try:
            if os.path.exists(backup_filename):
                os.remove(backup_filename)
            os.rename(filename, backup_filename)
        except Exception as e:
            print(f"Backup failed: {e}")

    all_results = []
    total = len(constituency_tuple)

    # 2. Use ThreadPoolExecutor with 5 workers
    # This is "polite" to the server and stable for Streamlit Cloud
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # Submit tasks: {Future: Constituency_ID}
        future_to_con = {
            executor.submit(update_election_count, con): con
            for con in constituency_tuple
        }

        for i, future in enumerate(concurrent.futures.as_completed(future_to_con), 1):
            con = future_to_con[future]
            try:
                data = future.result()
                if data and isinstance(data, list):
                    all_results.extend(data)

                # 3. Update Streamlit UI (Thread-safe in modern Streamlit)
                if st_progress and st_status:
                    # Update status text and progress bar
                    st_status.text(f"Getting {i}/{total}: {con}")
                    st_progress.progress(i / total)

            except Exception as e:
                print(f"Error scraping {con}: {e}")

    # 4. Optimized Batch Save
    if all_results:
        df = pd.DataFrame(all_results)

        # --- Crucial: Convert votes to numeric for proper sorting ---
        # This prevents '10' from appearing above '2' because of string sorting
        df['votes_int'] = df['votes'].apply(lambda x: int(str(x).replace(',', '')) if pd.notnull(x) else 0)

        # Sort: Constituency A-Z, then Votes High-to-Low
        df = df.sort_values(by=["Constituency", "votes_int"], ascending=[True, False])

        # Drop the helper column before saving
        df = df.drop(columns=['votes_int'])

        # Final write to disk (Single I/O operation)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        return True

    return False


if __name__ == "__main__":
    # get_all_voter_data()
    # get_party_list()
    update_election_count('kapilbstu3')
    # get_all_live_results()


