import xml.etree.ElementTree as ET
from xml.dom import minidom

def parse_xml_data(xml_data):
    d={}
    root=minidom.parseString(xml_data)
    candidate_pdf=root.getElementsByTagName("candidate_pdf")[0]
    description_1=root.getElementsByTagName("description_1")[0]
    description_2=root.getElementsByTagName("description_2")[0]
    d['candidate_pdf_key']=candidate_pdf.firstChild.data
    d['description_1']=description_1.firstChild.data
    d['description_2']=description_2.firstChild.data
    return d