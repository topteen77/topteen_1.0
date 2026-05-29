"""
Generate curated related-career suggestions from all_careers.csv.

Run: python careers/generate_related_careers_csv.py
Output: related_careers_curated.csv (id, career, cluster_id, related_career_ids)
"""

import csv
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "all_careers.csv"
OUT_PATH = ROOT / "related_careers_curated.csv"

GROUPS = [
    ("3d_anim", r"3d anim|animation designer|animator|motion graphic|vfx designer|multimedia artist|concept artist|generative.?ai artist|digital.?art & animation"),
    ("3d_print", r"3d print"),
    ("acting", r"^actor$|acting coach|theatre artist|theatre director|theatre stage|dramatherapist|stand.?up comedian|performance artist|casting director"),
    ("fashion", r"fashion|couturier|apparel production|textile designer|textile technologist|accessory designer|leather designer|sustainable.?fashion|hair stylist|make.?up artist"),
    ("graphic_ui", r"graphic designer|ui and ux|visual merchandiser|digital content strateg|interactive media designer|character designing"),
    ("fine_arts", r"fine artist|sculptor|photographer|photography designer|ceramic designer|glass designing|toy designer|craft designer|cartoonist|applied.?arts"),
    ("music", r"music director|music producer|music instructor|musician|musical.?instrument|singer|lyricist|music therapist|music teacher|music journalist|music critic|music composer|recording artist|disc jockey"),
    ("dance_choreo", r"\bdancer\b|dance instructor|dance teacher|ballet|choreographer"),
    ("film", r"film director|film maker|film & video|cinematograph|screenwriter|scriptwriter|documentary filmmaker|film critic|creative director|production designer|set designer|costume designer|stage manager"),
    ("media", r"journalist|news anchor|reporter|columnist|editorialist|critic\b|blogger|mass communication|public.?relations executive|media planner|media researcher|entertainment journalist|technology writer|web producer|podcast host|podcast producer"),
    ("ad_marketing", r"advertising|copywriter|brand manager|content.?marketing|digital.?marketing|marketing manager|marketing analyst|seo analyst|creator economy"),
    ("writing", r"content writer|academic writer|creative writer|copywriter|technical writer|technology writer|editor\b"),
    ("accounting", r"accountant|chartered accountant|certified public|auditor|forensic accountant|cost & works|acca|company secretary"),
    ("finance", r"finance analyst|finance consultant|finance controller|finance planner|financial advisor|financial planner|financial portfolio|financial risk|investment analyst|investment banker|wealth manager|stock broker|credit analyst|treasury|equity analyst|budget consultant|fraud examiner|financial planning & wealth"),
    ("banking", r"banker|banking|insurance consultant|commercial banker|retail banker|bpo executive"),
    ("actuary_insurance", r"actuary|insurance consultant|financial risk|actuar"),
    ("economics", r"economist|econometr|economic research|development economist|behavioural economist|public policy economist|urban or regional economist|trade.?policy|climate.*economist|energy economist|environmental economist|health economist|industrial economist|international trade economist|economic.?development planner"),
    ("tax", r"tax auditor|tax consultant|taxation lawyer"),
    ("fintech", r"fintech|blockchain auditor|crypto|digital.?economy|esg analyst|carbon credit"),
    ("law_general", r"advocate|lawyer|legal advisor|judge|judicial magistrate|paralegal|legal researcher|court reporter|professor - law"),
    ("law_corp", r"corporate lawyer|business lawyer|compliance & risk|patent lawyer|intellectual.?property|media lawyer|sports lawyer|space lawyer|cyber.?law|data.?privacy"),
    ("law_criminal", r"criminal lawyer|criminal investigator|criminologist|detective|forensic medicine"),
    ("law_civil", r"civil lawyer|family lawyer|immigration lawyer|labour lawyer|constitutional lawyer|disability rights"),
    ("civil_services", r"indian administrative|indian foreign service|indian economic service|indian audit|indian civil accounts|indian corporate law service|indian defence accounts|indian information service|indian judicial|indian medical service|indian postal|indian railway management|indian revenue service|indian statistical|indian trade service|state administrative|state civil|district magistrate|deputy commissioner|sub.?divisional|tehsildar|assistant commissioner|block development|staff selection commission|defence administrative|public sector undertaking|education administration|municipal administration|panchayati raj|social welfare|diplomat|central engineering service|central water engineering|state electricity|state forest service|state revenue service|public prosecutor|tehsildar"),
    ("police_defence", r"indian police|state police|police inspector|border security|central reserve police|intelligence officer|indian army|indian navy|indian naval|indian coast guard|armed forces medical|military engineer|defence analyst|security consultant|strategic affairs"),
    ("railway_govt", r"railway recruitment|railway service|irsee|irse|irsme|irsse|indian railways services"),
    ("agri_core", r"agricultur|agronom|agri.?business|agricultural economist|agricultural extension|agriculturalist|seed technologist|crop genomics|sericultur|viticultur|floricultur|apicultur|organic farming|poultry|dairy scientist|dairy product|dairy technology|hydroponics|vertical.*farm|urban.?farm|arborist|citricultur|dendrolog|pomolog"),
    ("agri_tech", r"agri.?fintech|agritech|agricultural gis|agricultural drone|phytopathologist|food process engineer|food research|food production manager|food safety|food technology|agriculture biotech|agrobiolog|food.?processing technician|farm.?machinery"),
    ("env_agri", r"conservation scientist|conservation officer|biodiversity|environmental impact|environmental restoration|environmental toxicologist|environmental auditor|ecosystem analyst|pollution control|waste management|forest conservation|wildlife conservation|marine conservation|renewable energy specialist|solar energy|wind energy|carbon footprint|climate change analyst|sustainability management"),
    ("vet_core", r"veterinary doctor|veterinary surgeon|veterinary technician|wildlife.*veterinarian|zoo veterinarian|aquatic veterinarian"),
    ("vet_specialist", r"veterinary anesthesiologist|veterinary cardiologist|veterinary dentist|veterinary dermatologist|veterinary nutritionist|veterinary oncologist|veterinary pathologist|veterinary pharmacologist|veterinary radiologist"),
    ("animal_care", r"animal breeder|animal trainer|animal welfare|animal research|animal hospital|pet groomer|aquacultur|hippolog|etholog|entomolog|herpetolog|zoophysiolog|arachnolog"),
    ("alt_med", r"acupuncturist|ayurvedic|homeopathic|naturopathic|yoga & wellness|yoga instructor|massage therapist"),
    ("physio_rehab", r"physiotherapist|physiotherapy assistant|occupational therapy|speech therapist|orthotist|prosthet|rehabilitation psychologist|rehabilitation engineer|behaviour therapist|cognitive behavioural|family therapist|substance abuse|mental health counsellor|sports physiotherapy"),
    ("audiology", r"audiologist|speech therapist|hearing"),
    ("nursing_emt", r"\bnurse\b|advance.?care paramedic|emergency.?medical technician|medical assistant|paramedical|geriatric care assistant"),
    ("nutrition", r"nutritionist|clinical nutritionist|geriatric nutritionist|paediatric nutritionist|sports nutritionist|nutrition & dietetics|biohacker|longevity"),
    ("pharma", r"pharmacist|pharmacolog|drug analyst|drug.?design"),
    ("diag_imaging", r"radiograph|sonograph|ct.?scan|mri technician|x.?ray|ech technologist|ecg technolog|eeg technolog|emg technolog|end technolog|diagnostic.?medical"),
    ("dialysis_renal", r"dialysis|nephrolog"),
    ("lab_path", r"laboratory technician|medical lab|pathologist|blood.?bank|forensic.?science technologist|haematology|clinical & aqua.?lab|gene.?sequencing"),
    ("surgery", r"general surgeon|orthopaedic surgeon|plastic surgeon|thoracic surgeon|vascular surgeon|neurosurgeon|robotic.?surgery"),
    ("physician", r"general physician|precision.*genomic.?medicine|personalized medicine"),
    ("cardio", r"cardiolog|cardiovascular technolog"),
    ("neuro", r"neurolog|neurosurgeon|neuropsychiatrist|neurodiagnostic|neurobiologist|neuroscience"),
    ("pediatrics", r"paediatric|neonatolog|child.?welfare"),
    ("womens_health", r"gynaecolog"),
    ("derm", r"dermatolog|burn.?care"),
    ("allergy_immuno", r"allergist|immunolog"),
    ("endocrine", r"endocrinolog"),
    ("ent_gi", r"gastroenterolog|hepatology|pulmonolog|urolog|endoscopy technolog"),
    ("eye", r"ophthalmolog|ophthalmic assistant|optometrist"),
    ("psychiatry", r"psychiatrist|clinical psychologist|psychopathologist|clinical physiologist"),
    ("oncology", r"oncolog|carcinolog|cancer.?research"),
    ("emergency", r"emergency medicine|intensive|icu technolog|anaesthes|anesthesia"),
    ("public_health", r"community medicine|epidemiolog|community.?health|healthcare administrator|hospital administrator|health.?care manager|telemedicine|digital health|health data analyst|healthtech"),
    ("dental", r"dentist|dental hygienist"),
    ("bio_sci", r"biologist|microbiolog|molecular biolog|cell biolog|zoolog|botanist|mycolog|virolog|bacteriolog|embryolog|cytolog|histolog|geneticist|genetic counsellor|bioinformatics|biophysics|morpholog|serolog|olfactolog|photobiolog|cryobiolog|future studies"),
    ("eco_sci", r"ecolog|hydrobiolog|marine biotech|algolog|aerobiolog|aerolog|atmospheric scientist|climatolog|microclimatolog|biometeorolog"),
    ("chem_phys", r"chemist\b|chemistry\)|physicist|computational chemist|biochemist|enzymolog|geochronolog|geohydrolog|flavourist"),
    ("earth_sci", r"geolog|geophysic|seismolog|volcanolog|glaciolog|meteorolog|oceanograph|paleontolog|mineralog|gemmolog|cartograph|selenologist"),
    ("space_sci", r"astronom|astrobiolog|cosmolog|nuclear physicist|quantum.?information|astronaut|astrogeolog|space technology"),
    ("aero_eng", r"aerospace engineer|aerospace.?material|airline pilot|air.?traffic|aircraft maintenance|aviation manager|astronaut"),
    ("mech_eng", r"mechanical engineer|manufacturing engineer|production engineer|mechatronics engineer|automobile engineer|power engineer|terminal.?operations|automation engineer"),
    ("civil_eng", r"civil engineer|structural engineer|construction engineer|transportation engineer|geotechnical|water resources engineer|central engineering service|central water engineering"),
    ("elec_eng", r"electrical engineer|electronics engineer|telecommunication|electric.?vehicle systems"),
    ("chem_eng", r"chemical engineer|petroleum engineer|polymer engineer|plastic engineer|metallurgical"),
    ("comp_eng", r"computer science engineer|software engineer|computer science\b|programmer"),
    ("bio_eng", r"biomedical engineer|biochemical engineer|biotechnology engineer|bionics|nanotechnology engineer|medical device software"),
    ("env_eng", r"environmental engineer|clean technology|renewable.?energy engineer"),
    ("marine_eng", r"marine engineer|naval architect|ocean engineer|merchant navy|marine & fisheries"),
    ("mining_eng", r"mining engineer|mineral engineer"),
    ("robotics_eng", r"robotics engineer|autonomous systems|autonomous vehicle|industrial engineer"),
    ("software_dev", r"software engineer|programmer|web developer|mobile app|software tester|software.?development technician|devops|site.?reliability|chatbot developer"),
    ("data_ai", r"data scientist|data analyst|data engineer|machine learning|artificial intelligence|ai.?ml|big data|prompt engineer|analytics professional|data.?science technician|ai ethics"),
    ("cloud_infra", r"cloud computing|cloud solutions|system analyst|database administrator|network architect|system.?administration|computer.?systems analyst|it manager|computer hardware technician"),
    ("cyber", r"cyber.?security|cybersecurity|information.?security|ethical hacking|cyber forensics|digital forensics"),
    ("blockchain_web3", r"blockchain developer|blockchain technician|smart contract|nft|web3"),
    ("iot_edge", r"internet of things|iot solutions|edge computing|digital twin|smart home|smart city technology|wearable technology|voice technology|digital transformation"),
    ("game_tech", r"game streamer|esports|professional gamer|sound designer for games|game developer"),
    ("arch", r"\barchitecture\b|architectural engineer|architecture engineer|research architect|restoration architect|heritage conservation architect|extreme architect|urban planning|landscape designing|interior designing|furniture designer|lighting & acoustics|bim manager|green building|smart city planner|spatial designer|parametric designer|exhibition designer"),
    ("construction_mgmt", r"construction manager|construction technology|building.?information|building.?construction technician"),
    ("industrial_design", r"automobile designer|design engineer|design management|design professional|design thinking"),
    ("teaching", r"\bteaching\b|teacher trainer|school administrator|special education|distance learning|e.?learning developer|instructional design|educational consultant|education officer|education policy|education inspector|curriculum designing|adult education|professors and lecturers|cultural program coordinator|digital humanities"),
    ("edu_support", r"career counselling|counselling\b|librarian|library network|edtech|educational technology|educational content|educational researcher|memory trainer|language trainer"),
    ("social_sci", r"sociolog|anthropolog|political scientist|historian|philolog|demographer|geographer|gender and women|public administration|social worker|human.?rights|behaviour analyst|psychologist\b|archaeolog|museology|museum curator|curator\b|heritage.?tourism|heritage & museum"),
    ("hospitality", r"hotel manager|restaurant manager|chef|culinary|catering|accomodation|hospitality consultant|tour operator|ecotourism|adventure.?tourism|theme.?park|cruise|resort manager|spa management|wedding planner|holiday consultant|mixologist|food stylist|conference manager|tourism marketing|health.?tourist|cultural tourism|bartender|baker & confectioner|beverage production|front.?office|ground.?operation|cabin crew|flight attendant"),
    ("aviation_ops", r"cabin crew|flight attendant|ground.?operation|aviation manager"),
    ("sports_core", r"\bathlete\b|sports coach|fitness trainer|fitness manager|strength & conditioning|sports manager|sports agent|sports analyst|sports psychologist|sports nutritionist|sports medicine|sports engineer|sports data|sports commentator|sports journalist|sports photographer|sports referee|sports event|sports facility|stadium manager|gym manager|sports administrator|sports entrepreneur|sports equipment|sports bio|sports technology|sports marketing|sports lawyer|athlete brand|athlete.?development"),
    ("vocational_trade", r"electrician|hvac|refrigeration|plumber|carpenter|glazier|painter & decorator|upholsterer|embroidery|tailor|screen printing|heavy equipment|machine operator|cnc machine|appliance repair|driving instructor|warehouse|inventory manager|production line supervisor|quality control inspector|waste management & recycling|water quality|cold chain|printing & publishing|upholsterer"),
    ("beauty_cosmo", r"beauty.?therapy|cosmetologist|nail technician"),
    ("auto_trade", r"automobile technician|ev.*service technician|drone pilot"),
    ("biz_mgmt", r"management consultant|operations manager|project management|strategic planning|change management|quality manager|training manager|human resource|supply.?chain|innovation lab|entrepreneurship|entrepreneur or business|crisis management|customer.?service|corporate.?social.?responsibility|product manager|talent manager|real.?estate manager|revenue.?management"),
    ("audio_media_tech", r"audio & video technologist|sound engineer|podcast & audio|digital photography"),
    ("research", r"research and development|clinical research"),
    ("csr_esg", r"corporate.?social.?responsibility|sustainability or.*esg manager"),
    ("community_media", r"community media"),
    ("functional_lang", r"functional.?english|functional.?hindi"),
    ("influencer_voc", r"influencer|content creation & social"),
    ("jewellery", r"jewellery|jewelry"),
    ("interpreter", r"interpreter|translator|linguist"),
    ("radiotherapy", r"radiotherapy|radiologist"),
    ("respiratory", r"respiratory therapist|pulmonolog"),
    ("orthotics", r"orthotic|orthotist|prosthet"),
    ("metaverse", r"metaverse|mixed reality"),
    ("mobile_repair", r"mobile phone repair|mobile.?communications technician"),
    ("manufacturing", r"manufacturing engineer"),
    ("materials_sci", r"materials.?science engineer"),
    ("mathematics", r"mathematician|statistician"),
    ("market_research", r"market.?research manager"),
    ("modelling", r"^modelling$"),
    ("home_science", r"home science"),
    ("horticulture", r"horticulturist"),
    ("housekeeping", r"housekeeping"),
    ("image_consult", r"image consultant"),
    ("intl_relations", r"international relations"),
    ("vocational_counsel", r"vocational counsellor"),
    ("voice_over", r"voice.?over|dubbing"),
    ("wedding_decor", r"wedding decor"),
    ("wind_solar", r"wind.?turbine|solar.?pv installer"),
    ("space_satellite", r"space.?systems|satellite engineer"),
    ("sports_med", r"sports.?medicine physician"),
    ("scientist_gen", r"^scientist$"),
    ("biological_sci", r"biological scientist"),
    ("fishery", r"fishery scientist"),
    ("soil_sci", r"soil scientist"),
    ("remote_sensing", r"remote.?sensing|earth.?observation"),
    ("irrigation", r"irrigation engineer"),
    ("optical_eng", r"optical engineer"),
    ("occupational_med", r"occupational medicine"),
    ("office_admin", r"office.?management|secretarial"),
    ("sme", r"small & medium.?enterprise"),
    ("telemarketing", r"telemarketer"),
    ("sales_mgr", r"sales manager"),
    ("tech_startup", r"tech startup founder"),
    ("radio_vj", r"radio jockey|video jockey"),
]

MANUAL = {
    1315: [1354, 1373, 1329, 1842, 1275],
    1302: [1312, 1307, 1353, 1341, 1367],
    1524: [1507, 1033, 1270, 1456, 1492, 1499],
    1126: [1799, 1810, 1135, 1800, 1131, 1121],
    1964: [1413, 1434, 1577, 1401, 1894],
    1175: [1140, 1151, 1137, 1812, 1168],
    1548: [2077, 1206, 1744, 2001, 1691],
    1467: [1904, 1886, 1947, 1460, 1077],
    1345: [1311, 1360, 1346, 1878, 1321],
    1342: [1381, 1306, 1324, 1880],
    28: [1733, 1419, 993, 1233, 1945, 1424],
    1569: [2018, 1553, 1997, 1559, 30, 1543],
    67: [1138, 1157, 1166, 1755, 1591],
    1647: [2014, 1668, 1687, 1649, 1239],
    41: [1507, 1499, 1503, 1524, 1033],
    1317: [1531, 1362, 1880, 1337, 1301],
    1376: [1346, 1380, 1321, 1370, 1367],
    1370: [1379, 1376, 1382, 1312, 1880],
    1359: [1369, 1371, 1864, 1796, 1346],
    2044: [2028, 1266, 1378, 1516, 1484],
    1401: [1418, 1413, 1588, 1438, 1964],
    1413: [1434, 1964, 1577, 1401, 1444],
    1488: [1527, 1489, 1490, 1494, 1578],
    2037: [1489, 1490, 2031, 1513, 80],
    1513: [1476, 2048, 1958, 1514, 1480],
    1577: [1413, 1964, 1434, 1583, 1420],
    2030: [1666, 1574, 1261, 1678, 1444],
    1672: [1685, 1817, 1113, 1989, 1155],
    1378: [1266, 1264, 2044, 2028, 95],
    1177: [1682, 1903, 1914, 1989, 1663],
    1682: [1177, 1903, 1914, 1989, 1663, 1991],
    1137: [1163, 1147, 1814, 1151, 1821],
    1491: [1527, 1399, 102, 1488, 2031],
    1612: [1626, 1593, 1940, 1928, 1411],
    1221: [1282, 1198, 1218, 1460, 1898],
    1382: [1312, 1307, 1347, 1374, 1302],
    1393: [1030, 1996, 1172, 1395, 1426, 1180],
    1846: [1227, 1260, 1907, 1910, 1242],
    1912: [1891, 1895, 1905, 1443, 1688],
    1951: [1409, 1950, 1952, 101, 1949],
    1220: [1517, 1589, 1586, 1225, 1446],
    1446: [1579, 1586, 1225, 1285, 1220],
    1907: [1568, 1242, 1247, 2006, 1528],
    1853: [1640, 1637, 1244, 85, 1201],
    1833: [1650, 1640, 1649, 41, 1021],
    1266: [1378, 1844, 2044, 2028, 1842],
    1838: [1853, 1640, 1244, 1825, 85],
    35: [38, 1709, 1077, 1726, 1545],
    37: [1709, 1724, 35, 38, 1739],
    1857: [1335, 1876, 1329, 1354, 1275],
    1796: [1369, 1359, 1864, 1876, 1882],
    1321: [1308, 1406, 1882, 1348, 1376],
    1257: [1575, 1210, 1267, 1236, 1259],
    1829: [1273, 1292, 1443, 1451, 1034],
    1249: [1238, 1362, 1286, 1264, 1128],
    1623: [1621, 1601, 1631, 1590, 1602, 1624],
    1605: [2017, 1191, 1541, 1390, 1180],
    1701: [1357, 1745, 1726, 49, 1883],
    1347: [1374, 1346, 1352, 1382, 1312, 1307],
    1374: [1347, 1352, 1382, 1312, 1307, 1302],
    1327: [1383, 1866, 1331, 1312, 1307, 1350],
    1383: [1327, 1866, 1331, 1312, 1307],
    1715: [1182, 1717, 1736, 1206, 1186],
    1690: [1186, 1212, 1717, 1736, 1200],
    1731: [2008, 1541, 2079, 30, 1072],
    1541: [2008, 2079, 1731, 2017, 1694],
    1294: [1859, 1337, 1860, 1274, 1880],
    1687: [1668, 1647, 2014, 1999, 1544],
    1404: [2075, 1645, 1652, 1424, 1233],
    2081: [1091, 1738, 1426, 1814, 1947],
    1116: [1154, 1150, 1173, 1757, 1145],
    1276: [1239, 1849, 1649, 1295, 1241],
    1252: [1215, 1431, 1411, 1943, 1257],
    1215: [1252, 1431, 1411, 1079, 1943],
    1244: [85, 1201, 2052, 1279, 1853],
    1646: [1640, 1637, 1653, 41, 1507],
    1259: [1282, 1194, 1200, 1230, 1228],
    1250: [1820, 1045, 1178, 1822, 1171],
    1742: [1732, 1746, 1123, 1712, 1700],
    1830: [1832, 1840, 1834, 1836, 1831],
    1222: [1052, 1518, 1225, 1270, 1503],
    1915: [1904, 1471, 1886, 1217, 1896],
    1144: [1297, 1142, 1162, 1263, 1246],
    1169: [1159, 1156, 1170, 1811, 1824],
    1358: [1314, 1855, 1337, 1880, 1362],
    1478: [1503, 1033, 1465, 1457, 1499],
    1962: [1409, 1955, 1946, 1080, 1963],
    1137: [1163, 1147, 1814, 1821, 1151],
    1529: [91, 1343, 1380, 1109, 49],
    1196: [1064, 1183, 1131, 1700, 1726, 1200],
    1132: [1128, 1286, 1722, 2049, 1135],
    95: [1876, 1335, 1378, 1266, 1264, 1794],
    1717: [1186, 1212, 1182, 1736, 1200, 1690],
    1849: [1649, 1638, 1276, 1239, 1657],
    1078: [1378, 2041, 2024, 1266, 1431],
    1613: [1621, 1932, 2012, 2004, 1623],
    1732: [1742, 1746, 1123, 1700, 1712],
    1954: [1426, 1612, 1437, 1816, 1947],
    1246: [1162, 1142, 1297, 1816, 1144],
    1411: [1079, 1252, 1215, 1431, 1401],
    1191: [2017, 1206, 1193, 1605, 2019, 1180],
    1484: [1214, 1512, 1288, 1516, 2041],
    1079: [1411, 1414, 1431, 1252, 1401],
    1562: [2015, 1528, 1570, 1104, 1825],
    1660: [1679, 1676, 1210, 1575, 1989],
    1549: [1554, 1553, 1538, 1709, 38],
    1705: [1714, 1153, 1148, 1724, 2080],
    1267: [1575, 111, 1210, 1236, 1581],
    1913: [1460, 1916, 1904, 1497, 1033],
    1916: [1913, 1460, 1218, 1904, 1497],
    1834: [1840, 1829, 1272, 1273, 1448],
    1272: [1542, 1834, 1829, 1273, 1451],
    992: [1525, 1522, 2039, 1500, 1476],
    1875: [1368, 1363, 1866, 1346, 1873],
    1241: [1295, 1276, 1301, 1239, 1663],
    1535: [1534, 2016, 1306, 1324, 1333],
    1879: [1310, 1854, 1351, 1213, 1258],
    1433: [1418, 1436, 1579, 1965, 1580],
    1314: [1357, 1367, 1341, 1302, 1312],
    1694: [1198, 2069, 1072, 1744, 2077],
    1878: [1360, 1345, 1311, 1880, 1337],
    1669: [1989, 1683, 1676, 1655, 1665],
    1738: [1091, 1726, 1700, 35, 49],
    1271: [1177, 1682, 2046, 1903, 1914],
    1061: [1180, 1206, 1717, 1196, 2055],
    1248: [1253, 1228, 2054, 2067, 1566],
    1559: [1997, 2018, 1569, 1550, 1533],
    1368: [1874, 1779, 1069, 1784, 1346],
    1714: [1705, 1153, 1603, 1148, 1691],
    1903: [1177, 1682, 1914, 1895, 1908],
    1572: [1575, 1210, 1678, 1219, 1147],
    1436: [1433, 1587, 1418, 1965, 1500],
    1356: [1080, 64, 1882, 1338, 1955],
    1500: [1525, 2035, 1495, 1436, 992],
    1848: [1032, 1658, 1644, 41, 1212],
    1262: [2054, 2067, 1228, 1253, 1566],
}


def load_careers():
    careers = []
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = int(row["id"].strip())
            name = row["career"].strip()
            cluster = int(row["cluster_id"].strip()) if row.get("cluster_id", "").strip() else None
            careers.append({"id": cid, "name": name, "cluster": cluster, "lower": name.lower()})
    return careers


def match_group(name_lower):
    for gid, pattern in GROUPS:
        if re.search(pattern, name_lower, re.I):
            return gid
    return None


def build_group_members(careers):
    members = defaultdict(list)
    for c in careers:
        gid = match_group(c["lower"])
        if gid:
            members[gid].append(c["id"])
    return members


def token_set(s):
    stop = {
        "or", "and", "the", "a", "an", "of", "in", "for", "via", "under", "india",
        "indian", "service", "services", "roles", "role", "level", "state", "central",
        "group", "assistant", "specialist", "professional", "technician", "technologist",
        "engineer", "manager", "officer", "executive", "consultant", "analyst", "developer",
        "designer", "scientist", "doctor", "teacher", "instructor", "integrated",
    }
    return set(re.findall(r"[a-z0-9]+", s.lower())) - stop


def name_similarity(a, b):
    ta, tb = token_set(a), token_set(b)
    if not ta or not tb:
        return 0
    return len(ta & tb) / len(ta | tb)


def pick_related(career, careers_by_id, group_members, max_n=6):
    cid = career["id"]
    if cid in MANUAL:
        return [x for x in MANUAL[cid] if x != cid][:max_n]

    gid = match_group(career["lower"])
    candidates = []
    if gid and gid in group_members:
        candidates = [x for x in group_members[gid] if x != cid]

    if len(candidates) < 6:
        scored = []
        for other in careers_by_id.values():
            if other["id"] == cid:
                continue
            sim = name_similarity(career["name"], other["name"])
            threshold = 0.22 if len(candidates) < 3 else 0.34
            if sim >= threshold:
                scored.append((sim, other["id"]))
        scored.sort(reverse=True)
        for _, oid in scored[:20]:
            if oid not in candidates:
                candidates.append(oid)

    def sort_key(oid):
        o = careers_by_id[oid]
        sim = name_similarity(career["name"], o["name"])
        same_cluster = 0.05 if career["cluster"] and o["cluster"] == career["cluster"] else 0
        return sim + same_cluster

    candidates = sorted(set(candidates), key=sort_key, reverse=True)

    if career["cluster"] == 28 and not gid:
        candidates = [x for x in candidates if name_similarity(career["name"], careers_by_id[x]["name"]) >= 0.42]
    # Do not link human health careers to veterinary specialties
    if career["cluster"] == 28:
        vet_only = {1121, 1127, 1129, 1130, 1798, 1802, 1805, 1806, 1807}
        candidates = [x for x in candidates if x not in vet_only or careers_by_id[x]["cluster"] == 28]

    rel = candidates[:max_n]
    if len(rel) < 3 and len(candidates) >= 3:
        rel = candidates[:3]
  # Pad tiny groups (e.g. paired specialist/technician) with same-cluster neighbors
    if len(rel) < 3 and career["cluster"]:
        for other in careers_by_id.values():
            if other["id"] == cid or other["id"] in rel:
                continue
            if other["cluster"] != career["cluster"]:
                continue
            if name_similarity(career["name"], other["name"]) >= 0.12:
                rel.append(other["id"])
            if len(rel) >= 3:
                break
    return rel[:max_n]


def main():
    careers = load_careers()
    careers_by_id = {c["id"]: c for c in careers}
    group_members = build_group_members(careers)

    rows_out = []
    for c in careers:
        rel = pick_related(c, careers_by_id, group_members)
        rows_out.append({
            "id": c["id"],
            "career": c["name"],
            "cluster_id": c["cluster"] or "",
            "related_career_ids": ",".join(str(x) for x in rel),
        })

    with OUT_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "career", "cluster_id", "related_career_ids"])
        w.writeheader()
        w.writerows(rows_out)

    empty = sum(1 for r in rows_out if not r["related_career_ids"])
    print(f"Wrote {OUT_PATH}: {len(rows_out)} rows, {len(rows_out) - empty} with related, {empty} empty")


if __name__ == "__main__":
    main()