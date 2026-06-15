with open('vanta-wear.html', 'r', encoding='utf-8') as f:
    text = f.read()
import re
match = re.search(r'  <div class=" dropdown\ id=\dropdown\>.*? </div>\n</div>\n', text, re.DOTALL)
if match:
 dropdown_html = match.group(0)
 text = text.replace(dropdown_html, '')
 text = text.replace('</nav>', dropdown_html + '</nav>')
 with open('vanta-wear.html', 'w', encoding='utf-8') as f:
 f.write(text)
 print('Success')
else:
 print('Not found')
