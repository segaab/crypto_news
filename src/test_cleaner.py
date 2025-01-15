import xml.etree.ElementTree as ET
import json
import re
import html
from bs4 import BeautifulSoup

class XMLEncodedContentCleaner:
    def __init__(self):
        pass

    @staticmethod
    def detect_encoded_elements(xml_data):
        """
        Detect elements with the ':encoded' suffix in the XML structure.
        """
        encoded_elements = []
        try:
            tree = ET.ElementTree(ET.fromstring(xml_data))
            for elem in tree.iter():
                if ":encoded" in elem.tag:
                    encoded_elements.append(elem)
        except ET.ParseError as e:
            print(f"XML Parsing Error: {e}")
        return encoded_elements

    @staticmethod
    def clean_encoded_content(encoded_element):
        """
        Clean the content of the encoded element by:
        - Unescaping HTML entities
        - Removing HTML tags using BeautifulSoup
        - Stripping leading and trailing whitespace
        """
        if encoded_element.text:
            # Unescape HTML entities
            unescaped_content = html.unescape(encoded_element.text)
            # Remove HTML tags using BeautifulSoup
            soup = BeautifulSoup(unescaped_content, 'html.parser')
            cleaned_content = soup.get_text(separator=' ', strip=True)
            # Strip leading and trailing whitespace
            cleaned_content = cleaned_content.strip()
            return cleaned_content
        return None

    @staticmethod
    def compile_to_json(encoded_elements):
        """
        Compile the cleaned content of encoded elements into JSON format.
        """
        result = {}
        for elem in encoded_elements:
            # Remove namespace prefix
            if ':' in elem.tag:
                tag_name = elem.tag.split(':')[-1]
            else:
                tag_name = elem.tag
            cleaned_content = XMLEncodedContentCleaner.clean_encoded_content(elem)
            if cleaned_content:
                result[tag_name] = cleaned_content
        return json.dumps(result, indent=4, ensure_ascii=False)

    def process_xml(self, xml_data):
        """
        Detect, clean, and compile encoded elements into JSON.
        """
        encoded_elements = self.detect_encoded_elements(xml_data)
        if not encoded_elements:
            return "No encoded elements found."
        json_output = self.compile_to_json(encoded_elements)
        return json_output

# Example Usage
if __name__ == "__main__":
    sample_xml = """
    <root>
        <content:encoded>
            <p>South Koreans are paying a full 3% more to buy bitcoin (BTC) than their U.S. counterparts as they seek protection from the plummeting won, CryptoQuant data show.</p>
            <p>Priced in won, the largest cryptocurrency is valued at 145,000,000 ($98,600) on the country's largest crypto exchange, Upbit. That compares with about $96,700 on Coinbase (COIN).</p>
            <p>The move follows a vote by the South Korean parliament to impeach Han Duck-soo, the prime minister and acting president, just weeks after impeaching President Yoon Suk Yeol. The won slumped a 15-year low against the dollar.</p>
            <p>"This unfolding saga is fundamentally about election<a href="https://x.com/dgt10011/status/1872245229795078403" target="_blank"> fraud and the erosion of trust</a> in South Korea’s National Election Commission (NEC)," said Jeff Park, head of alpha strategies at investment manager Bitwise, in a post on X. "The use of impeachment as a political tool, combined with allegations of foreign election interference, underscores the fragility of democracy in the face of disinformation. This is not just a Korean story; it’s a warning for democracies worldwide."</p>
        </content:encoded>
    </root>
    """
    
    cleaner = XMLEncodedContentCleaner()
    result = cleaner.process_xml(sample_xml)
    print("JSON Output:")
    print(result)