import sys
import xml.etree.ElementTree as ET
import datetime
import logging
import re
import os
from urllib.request import urlopen, Request
import pandas as pd
from bs4 import BeautifulSoup

# 1. Setup paths relative to the script location
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
logfile = os.path.join(BASE_DIR, 'eru.log')
output_file = os.path.join(BASE_DIR, 'eru_licence_zpracovane.xlsx')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(logfile, encoding='utf-8'),
        logging.StreamHandler() # This allows you to see logs in GitHub Action console
    ]
)

# 2. Handle Date Input
# Check if a date was passed from GitHub Actions
if len(sys.argv) > 1 and sys.argv[1].strip() != "":
    dt = sys.argv[1].strip()
    logging.info(f"Using manual date input: {dt}")
else:
    dt = datetime.date.today().strftime('%d%m%Y')
    logging.info(f"Using default current date: {dt}")

urladdress = f"https://eru.gov.cz/seznam-drzitelu-licenci-uznani-opravneni-podnikat-ke-dni-{dt}"


# Spoof a browser header to prevent 403 Forbidden errors
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

try:
    req = Request(urladdress, headers=headers)
    with urlopen(req) as html_page:
        logging.info(f'Stranka stazena: {urladdress}')
        soup = BeautifulSoup(html_page, 'html.parser')

        # get links for specific license files
        xmlfiles = {}
        # Pattern covers specific license types (11, 12, 14, 24, 31, 32)
        link_pattern = re.compile(r"/lic((11)|(12)|(14)|(24)|(31)|(32))")
        
        for link in soup.findAll('a', attrs={'href': link_pattern}):
            lnk = link.get('href')
            if not lnk.startswith('http'):
                lnk = 'https://www.eru.cz' + lnk
            
            desc = link.text.strip()
            if lnk not in xmlfiles:
                xmlfiles[lnk] = desc

        if not xmlfiles:
            logging.warning("Nenalezeny zadne odkazy na XML soubory.")
        
        # 3. Parse XML files
        licence_data = []
        for xml_url, description in xmlfiles.items():
            try:
                xml_req = Request(xml_url, headers=headers)
                with urlopen(xml_req) as f:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    for child in root:
                        # Merge attributes into a dictionary
                        entry = child.attrib.copy()
                        entry['src_type'] = description
                        entry['src_file'] = xml_url
                        entry['extraction_date'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        licence_data.append(entry)
            except Exception as e:
                logging.error(f"Chyba pri zpracovani XML {xml_url}: {e}")

        # 4. Save to Excel
        if licence_data:
            df = pd.DataFrame(licence_data)
            df.to_excel(output_file, index=False, engine='openpyxl')
            logging.info(f"Ulozeno {len(df)} zaznamu do {output_file}")
        else:
            logging.error("Zadna data nebyla stazena.")

except Exception as e:
    logging.error(f"Hlavni proces selhal: {e}")
