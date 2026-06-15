from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import psycopg2
from psycopg2.extras import DictCursor
import jwt
import datetime
import json
import os
import uuid
from functools import wraps
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
CORS(app) # Allow all origins for now

SECRET_KEY = "vanta_super_secret_key"
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
DB_PARAMS = {
    'dbname': 'vantawear',
    'user': 'postgres',
    'password': '1234',
    'host': 'localhost',
    'port': '5432'
}

def get_db():
    return psycopg2.connect(**DB_PARAMS)

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token or not token.startswith("Bearer "):
            return jsonify({'message': 'Token is missing or invalid'}), 401
        
        token = token.split(" ")[1]
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        except:
            return jsonify({'message': 'Token is invalid or expired'}), 401
            
        return f(*args, **kwargs)
    return decorated

@app.route('/api/products', methods=['GET'])
def get_products():
    conn = get_db()
    c = conn.cursor(cursor_factory=DictCursor)
    c.execute("SELECT * FROM products ORDER BY created_at DESC NULLS LAST, id DESC")
    rows = c.fetchall()
    conn.close()
    
    products = []
    for r in rows:
        p = dict(r)
        
        # PostgreSQL column name mappings (PG lowercases unquoted columns)
        p['desc'] = p.pop('desc_text', None)
        p['similar'] = p.pop('similar_products', None)
        p['imageUrl'] = p.pop('imageurl', None)
        p['ratingCount'] = p.pop('ratingcount', None)
        p['combineWith'] = p.pop('combinewith', None)
        
        # Parse JSON fields with null checks
        p['sizes'] = json.loads(p['sizes']) if p['sizes'] else []
        p['stock'] = json.loads(p['stock']) if p['stock'] else {}
        p['combineWith'] = json.loads(p['combineWith']) if p['combineWith'] else []
        p['similar'] = json.loads(p['similar']) if p['similar'] else []
        # New hover & colors fields
        p['imageUrlHover'] = p.pop('imageurl_hover', None)
        colors_val = p.pop('colors', None)
        if isinstance(colors_val, str):
            p['colors'] = json.loads(colors_val) if colors_val else []
        else:
            p['colors'] = colors_val or []
        
        products.append(p)
        
    return jsonify(products)

@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.json
    user_id = data.get('userId')
    
    # Try extracting user_id from token if present
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if token:
        try:
            decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            user_id = decoded['user_id']
        except:
            pass
            
    items = data.get('items', [])
    conn = get_db()
    c = conn.cursor(cursor_factory=DictCursor)
    
    # 1. Start transaction to check/reduce stock
    try:
        c.execute("BEGIN")
        
        items = data.get('items', [])
        for item in items:
            c.execute("SELECT stock FROM products WHERE id = %s", (item['productId'],))
            row = c.fetchone()
            if not row:
                raise Exception(f"Product {item['productId']} not found")
            
            stock = json.loads(row['stock'])
            sz = item['size']
            qty = item['qty']
            
            if stock.get(sz, 0) < qty:
                raise Exception(f"Yetersiz stok: {item['name']} - Beden: {sz}")
                
            stock[sz] -= qty
            c.execute("UPDATE products SET stock = %s WHERE id = %s", (json.dumps(stock), item['productId']))
            
        # 2. Create order
        c.execute('''
            INSERT INTO orders (sessionId, userId, customerName, address, items, total, shipping, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            data.get('sessionId'),
            str(user_id) if user_id else None,
            data.get('customerName'),
            data.get('address'),
            json.dumps(items),
            data.get('total'),
            data.get('shipping'),
            'pending'
        ))
        
        c.execute("COMMIT")
        conn.close()
        return jsonify({'success': True, 'message': 'Sipariş alındı'})
        
    except Exception as e:
        c.execute("ROLLBACK")
        conn.close()
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/orders/<int:order_id>/cancel', methods=['POST'])
def cancel_order(order_id):
    conn = get_db()
    c = conn.cursor(cursor_factory=DictCursor)
    try:
        c.execute("BEGIN")
        c.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
        order = c.fetchone()
        
        if not order:
            raise Exception("Sipariş bulunamadı")
        if order['status'] == 'canceled':
            raise Exception("Bu sipariş zaten iptal edilmiş")
            
        items = json.loads(order['items'])
        for item in items:
            c.execute("SELECT stock FROM products WHERE id = %s", (item['productId'],))
            row = c.fetchone()
            if row:
                stock = json.loads(row['stock'])
                sz = item['size']
                stock[sz] = stock.get(sz, 0) + item['qty']
                c.execute("UPDATE products SET stock = %s WHERE id = %s", (json.dumps(stock), item['productId']))
                
        c.execute("UPDATE orders SET status = 'canceled', updatedAt = CURRENT_TIMESTAMP WHERE id = %s", (order_id,))
        c.execute("COMMIT")
        conn.close()
        return jsonify({'success': True, 'message': 'Sipariş iptal edildi, stok geri eklendi.'})
        
    except Exception as e:
        c.execute("ROLLBACK")
        conn.close()
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/newsletter', methods=['POST'])
def add_newsletter():
    data = request.json
    email = data.get('email')
    if not email or '@' not in email:
        return jsonify({'success': False, 'message': 'Geçersiz e-posta'}), 400
        
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO newsletter (email) VALUES (%s)", (email,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Kaydolundu!'})

@app.route('/api/audit', methods=['POST'])
def log_audit():
    data = request.json
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO audit_logs (action, data, userId, sessionId, userAgent) VALUES (%s, %s, %s, %s, %s)",
              (data.get('action'), json.dumps(data.get('data')), data.get('userId'), data.get('sessionId'), data.get('userAgent')))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/chat', methods=['POST'])
def handle_chat():
    data = request.json
    msg = data.get('message', '').lower()
    
    # MEGA AI SIMULATION LOGIC
    import random
    import re
    conn = get_db()
    c = conn.cursor(cursor_factory=DictCursor)
    c.execute("SELECT id, name, price, barcode FROM products LIMIT 50")
    products = c.fetchall()
    conn.close()
    
    def make_link(p):
        return f'<a href="javascript:void(0)" onclick="openProductPage({p['id']})" style="color:var(--black);font-weight:800;text-decoration:underline">{p['name']}</a>'

    def make_cart_btn(p):
        return f'<br><br><button onclick="addBag({p['id']}); openCart()" style="background:#111;color:#fff;border:none;padding:6px 12px;border-radius:4px;cursor:pointer;font-weight:600;font-size:11px;letter-spacing:0.5px">🛒 Hemen Sepete Ekle</button>'

    def find_p(kws):
        for p in products:
            if any(k in p['name'].lower() for k in kws):
                return p
        return products[0] if products else None

    reply = ""
    msg_low = msg.lower()
    
    # --- 1. CHITCHAT & IDENTITY ---
    if any(w in msg_low for w in ['nasılsın', 'naber', 'ne haber', 'napıyorsun', 'ne yapıyorsun']):
        reply = "Harikayım! Vanta Wear'ın dijital dünyasında yeni trendleri inceliyordum. Sen nasılsın, bugün tarzına nasıl bir dokunuş yapmak istersin?"
    elif any(w in msg_low for w in ['adın ne', 'kimsin', 'sen nesin', 'robot musun']):
        reply = "Ben VantaAi! Vanta Wear'ın yapay zeka tabanlı kişisel stil danışmanıyım. Kodlardan oluşuyor olabilirim ama stil konusunda oldukça iddialıyım. 😎"
    elif any(w in msg_low for w in ['harikasın', 'süpersin', 'teşekkür', 'sağol']):
        reply = "Ne demek, her zaman buradayım! Tarzını daha da ileriye taşımak için ne zaman yardıma ihtiyacın olursa bana yazabilirsin. 🖤"
    elif any(w in msg_low for w in ['vanta', 'siyah', 'karanlık', 'tema']):
        reply = "Bizde siyah bir renk değil, bir yaşam tarzıdır! 😎 Işığın bile kaçamadığı o derin, efsanevi Vanta karanlığını sokak stiline uyarlıyoruz. Üzerine başka renk tanımıyoruz."
    elif any(w in msg_low for w in ['renkli', 'kırmızı', 'sarı', 'mavi', 'pembe', 'canlı']):
        reply = "Renkli mi? Biz o defteri çoktan kapattık... Siyahın asaleti varken diğer renkler sadece detaydır. Ama merak etme, karanlık tarafımız sana çok yakışacak! 🦇"
    elif any(w in msg_low for w in ['şaka yap', 'espri', 'sıkıldım', 'eğlendir']):
        reply = "Madem öyle: Batman Vanta Wear giyene kadar sadece sıradan bir yarasaydı... 😎 Şaka bir yana, ütü yapmayı sevmeyenler için 'Oversize' ve 'Kırışık Keten' trendleri icat edilmiştir! Bence harika bir bahane, değil mi?"
        
    # --- 2. OCCASIONS (ETKİNLİKLER) ---
    elif any(w in msg_low for w in ['randevu', 'date', 'buluşma', 'kız arkadaş', 'sevgiliyle']):
        p = find_p(['keten', 'gömlek', 'sade'])
        reply = f"Randevu için çok abartılı olmayan ama özenli duran bir tarz idealdir. Vanta kalıbıyla dikkat çeken {make_link(p)} mükemmel bir seçim olur. İlk izlenim önemlidir! {make_cart_btn(p)}"
    elif any(w in msg_low for w in ['konser', 'festival', 'parti', 'gece']):
        p = find_p(['siyah', 'deri', 'graphic', 'baskılı'])
        reply = f"Konser ve festival enerjisini yansıtacak cool ve iddialı bir parça arıyorsan {make_link(p)} tam sana göre. Rahat hareket ederken tarzından ödün vermezsin. 🤘 {make_cart_btn(p)}"
    elif any(w in msg_low for w in ['okul', 'üniversite', 'kampüs']):
        p = find_p(['hoodie', 'eşofman', 'basic'])
        reply = f"Okul için rahatlık her şeydir. Bütün gün kampüste koştururken seni rahat ettirecek ama stil duracak {make_link(p)} modeline kesinlikle göz atmalısın. {make_cart_btn(p)}"
        
    # --- 3. BODY TYPE & FIT ---
    elif any(w in msg_low for w in ['kısa boylu', 'boyum kısa']):
        reply = "Kısa boyluysan üst ve alt giyimde birbiriyle uyumlu, kontrast yaratmayan renkler seçmelisin (Örn: Siyah üst, siyah alt). Ayrıca aşırı bol (oversize) yerine 'Slim' veya 'Regular' kalıplar boyunu daha uzun gösterir!"
    elif any(w in msg_low for w in ['göbek', 'kilolu', 'geniş']):
        reply = "Fazlalıkları gizlemek için dar kalıplardan ve yatay çizgili desenlerden uzak durmalısın. Koyu renkler ve Vanta Wear'ın 'Oversize' kalıplı tişörtleri omuzlarını geniş gösterip alt kısmı mükemmel toparlar!"
        
    # --- 4. ORDER & SUPPORT ---
    elif re.search(r'\b\d{5}\b', msg_low) and any(w in msg_low for w in ['sipariş', 'kargo', 'nerede']):
        order_num = re.search(r'\b\d{5}\b', msg_low).group(0)
        reply = f"📦 {order_num} numaralı siparişini kontrol ettim. Siparişin yola çıkmış ve kurye dağıtımında görünüyor! Bugün veya en geç yarın sana ulaşacaktır."
    elif any(w in msg_low for w in ['yanlış', 'defolu', 'hasarlı', 'kötü']):
        reply = "Bunu duyduğuma çok üzüldüm. Vanta Wear'da müşteri memnuniyeti her şeydir! Lütfen ürünün fotoğrafını info@vantawear.com adresine sipariş numaranla ilet, anında ücretsiz değişim veya para iadesi yapalım."
    elif any(w in msg_low for w in ['yıkama', 'nasıl yıkanır', 'ütü', 'çeker mi']):
        reply = "Ürünlerimiz premium kumaştan üretilmiştir. Uzun ömürlü kullanım için 30 derecede tersten yıkamanı ve kurutma makinesi kullanmamanı tavsiye ederim. Baskılı ürünleri tersten ütülemeyi unutma!"
        
    # --- 5. SIZE CONSULTANT ---
    elif 'boyum' in msg_low and 'kilom' in msg_low:
        boy_m = re.search(r'boyum.*?(\d{3})', msg_low)
        kilo_m = re.search(r'kilom.*?(\d{2,3})', msg_low)
        if boy_m and kilo_m:
            kilo = int(kilo_m.group(1))
            if kilo < 65: beden = 'S'
            elif kilo < 75: beden = 'M'
            elif kilo < 85: beden = 'L'
            elif kilo < 95: beden = 'XL'
            else: beden = 'XXL'
            reply = f"📏 Boy-kilo oranına göre Vanta kalıplarında sana en uygun beden **{beden} Beden** olacaktır. Oversize durmasını istersen bir beden büyük de alabilirsin."
        else:
            reply = "Bedenini tam hesaplamam için boyunu ve kilonu sayısal olarak yazmalısın (Örn: Boyum 180 kilom 80)."

    # --- 6. COLORS ---
    elif any(w in msg_low for w in ['siyah', 'karanlık', 'dark']):
        p = find_p(['siyah', 'koyu'])
        reply = f"Siyahın asilliği tartışılmaz. Tam bir Vanta ruhu! Koleksiyonumuzdaki {make_link(p)} siyah tutkunları için özel tasarlandı. {make_cart_btn(p)}"
    elif any(w in msg_low for w in ['beyaz', 'açık', 'ferah']):
        p = find_p(['beyaz', 'açık'])
        reply = f"Ferah ve temiz bir görünüm arıyorsan beyaz en iyi tercihtir. Özellikle {make_link(p)} yaz ayları için kurtarıcı bir parçadır. {make_cart_btn(p)}"
    elif any(w in msg_low for w in ['gri', 'gray', 'grey', 'küllü']):
        p = find_p(['gri', 'küllü'])
        reply = f"Gri tonları her mevsim şık ve risksiz bir tercihtir. Özellikle senin için seçtiğim {make_link(p)} dolabının vazgeçilmezi olacak! {make_cart_btn(p)}"
    elif any(w in msg_low for w in ['kırmızı', 'bordo', 'canlı']):
        p = find_p(['kırmızı', 'bordo'])
        reply = f"İddialı ve enerjik! Bu tonlar tarzına güç katar. Örneğin {make_link(p)} modelimiz tam olarak bu enerjiyi yansıtıyor. {make_cart_btn(p)}"
    elif any(w in msg_low for w in ['mavi', 'lacivert', 'blue']):
        p = find_p(['mavi', 'lacivert'])
        reply = f"Mavi, hem sakin hem de cool bir görünüm verir. Denim uyumuyla harika duracak olan {make_link(p)} modelini kesinlikle öneririm. {make_cart_btn(p)}"
        
    # --- 7. ENGLISH LANGUAGE ---
    elif any(w in msg_low for w in ['hello', 'hi ', 'i need', 'looking for', 't-shirt', 'pants', 'shipping']):
        p = find_p(['tişört', 'jean'])
        reply = f"Hello! Welcome to Vanta Wear. If you are looking for premium streetwear, I highly recommend our {make_link(p)}. We offer fast shipping worldwide! {make_cart_btn(p)}"
        
    # --- 8. OUTFIT RATING ---
    elif any(w in msg_low for w in ['giydim', 'nasıl olmuş', 'sence nasıl', 'kombin yaptım']):
        p = find_p(['ceket', 'mont', 'aksesuar'])
        reply = f"⭐ Hayal ettim de, kombinin gayet başarılı duruyor, net 8/10 veririm! Ama bu kombini bir üst seviyeye (10/10) taşımak istersen üzerine kesinlikle {make_link(p)} eklemelisin. Bütün havayı değiştirecektir. {make_cart_btn(p)}"
        
    # --- 9. PROMO / BARGAINING ---
    elif any(w in msg_low for w in ['pahalı', 'indirim yok mu', 'öğrenci', 'kodu', 'indirim kodu']):
        reply = "💸 Seni kırmak hiç istemem! Sadece sana özel ve kısa bir süre geçerli %10 indirim kodu oluşturdum: **VANTA-AI-10**. Bu kodu sepette uygulayabilirsin!"
        
    # --- 10. MOOD / WEATHER ---
    elif any(w in msg_low for w in ['yorgunum', 'sakin', 'kötü', 'hastayım']):
        p = find_p(['hoodie', 'eşofman', 'bol'])
        reply = f"🎭 Anlıyorum, bugün rahat hissetmek senin de hakkın. Seni sıkmayacak dökümlü bir parça olan {make_link(p)} gününü kurtarabilir. Geçmiş olsun! {make_cart_btn(p)}"
    elif any(w in msg_low for w in ['enerjiğim', 'mutlu', 'dışarı', 'heyecanlı']):
        p = find_p(['kırmızı', 'graphic', 'şort', 'baskılı'])
        reply = f"🔥 Harika bir enerji! Bu enerjini dışarı yansıtacak iddialı bir parça olan {make_link(p)} bugün tam sana göre. {make_cart_btn(p)}"
    elif any(w in msg_low for w in ['antalya', 'izmir', 'sıcak', 'yaz', 'güneş']):
        p = find_p(['şort', 'atlet', 'keten'])
        reply = f"☀️ Orası şu an epey sıcaktır! Tam yazlık, nefes alan pamuklu {make_link(p)} modelimiz seni çok rahat ettirir. {make_cart_btn(p)}"
    elif any(w in msg_low for w in ['erzurum', 'ankara', 'soğuk', 'kış', 'kar']):
        p = find_p(['mont', 'hoodie', 'ceket'])
        reply = f"❄️ Sıkı giyinmen gerek! Soğuk havalara karşı Vanta imzalı kalın ve sıcak tutan {make_link(p)} modelimiz seni sıcacık tutacaktır. {make_cart_btn(p)}"
        
    # --- 11. SUSTAINABILITY ---
    elif any(w in msg_low for w in ['vegan', 'sürdürülebilir', 'çevre', 'doğa', 'pamuk']):
        reply = "🌱 Vanta Wear olarak gezegeni önemsiyoruz. Ürünlerimizin büyük çoğunluğu %100 organik pamuk ve çevre dostu yıkama teknikleriyle üretilmektedir. Deri ceketlerimiz ise hayvanlara zarar vermeden, tamamen vegan deriden yapılmıştır!"
        
    # --- 12. RETURN POLICY ---
    elif any(w in msg_low for w in ['iade', 'değişim', 'müşteri hizmetleri', 'geri ver']):
        reply = "🔄 Hiç merak etme! Ürünlerimizi 14 gün içinde, kullanılmamış ve etiketleri koparılmamış şekilde ücretsiz iade edebilir veya değiştirebilirsin. Faturanın altındaki iade kodunu Yurtiçi Kargo'ya vermen yeterli."

    # --- 13. NORMAL GIFT / BASIC CLOTHING ---
    elif any(w in msg_low for w in ['hediye', 'armağan']):
        p = find_p(['tişört', 'keten', 'jean'])
        reply = f"🎁 Harika bir hediye arayışındasın! Müşterilerimizin hediye olarak en çok tercih ettiği ürün {make_link(p)} modelidir. Eminim çok beğenecektir. {make_cart_btn(p)}"
    elif any(w in msg_low for w in ['pantolon', 'jean', 'kargo']):
        p = find_p(['jean', 'kargo'])
        reply = f"👖 Pantolon arayışındasın! Sana en çok satan modelimiz olan {make_link(p)}'i önerebilirim. Kesimi tam istediğin gibi cool duracaktır. {make_cart_btn(p)}"
    elif any(w in msg_low for w in ['tişört', 'tshirt', 'üst']):
        p = find_p(['tişört', 'crop'])
        reply = f"👕 Klasik ama vazgeçilmez! Dolabında her şeyle uyum sağlayacak kaliteli bir tişört arıyorsan {make_link(p)} harika bir tercih olur. {make_cart_btn(p)}"

    else:
        # --- 14. BARCODE SEARCH ---
        barcode_match = re.search(r'\d{8,}', msg_low)
        if barcode_match:
            b_code = barcode_match.group(0)
            p = next((p for p in products if p.get('barcode') and b_code in p['barcode']), None)
            if p:
                reply = f"Barkodu buldum! Aradığın ürün tam olarak bu: {make_link(p)}. Hemen detaylarına bakabilirsin. {make_cart_btn(p)}"
            else:
                reply = "Bu barkoda ait bir ürün veri tabanımızda maalesef bulamadım."
        else:
            # --- 15. DIRECT PRODUCT NAME SEARCH FALLBACK ---
            p = next((p for p in products if any(word in p['name'].lower() for word in msg_low.split() if len(word) > 3)), None)
            if p:
                reply = f"Sanırım tam olarak şu üründen bahsediyorsun: {make_link(p)}. Detaylarını inceleyebilirsin! {make_cart_btn(p)}"
            else:
                # --- 16. THE ULTIMATE FALLBACK ---
                reply = "Hımm, bunu tam anlayamadım. Ama bana Vanta ile ilgili her şeyi sorabilirsin! Örneğin:<br>- 'Adın ne?' veya 'Nasılsın?'<br>- 'Boyum 180 kilom 80'<br>- 'Düğüne gideceğim ne giyeyim?'<br>- 'Göbekliyim ne önerirsin?'<br>- 'Siyah tişört arıyorum'<br>- 'Fiyatlar pahalı'"

    import time
    time.sleep(1) # Simulate thinking
    return jsonify({'success': True, 'reply': reply})

# ADMIN API
@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    if data.get('password') == 'vanta2025admin':
        token = jwt.encode({'user': 'admin', 'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)}, SECRET_KEY, algorithm="HS256")
        return jsonify({'token': token})
    return jsonify({'message': 'Invalid credentials'}), 401

@app.route('/api/admin/orders', methods=['GET'])
@token_required
def admin_get_orders():
    conn = get_db()
    c = conn.cursor(cursor_factory=DictCursor)
    c.execute("SELECT * FROM orders ORDER BY createdat DESC")
    rows = c.fetchall()
    conn.close()
    
    orders = []
    for r in rows:
        o = dict(r)
        o['sessionId'] = o.pop('sessionid', None)
        o['userId'] = o.pop('userid', None)
        o['customerName'] = o.pop('customername', None)
        o['createdAt'] = o.pop('createdat', None)
        o['updatedAt'] = o.pop('updatedat', None)
        o['items'] = json.loads(o['items']) if o['items'] else []
        orders.append(o)
    return jsonify(orders)

@app.route('/api/admin/audit', methods=['GET'])
@token_required
def admin_get_audit():
    conn = get_db()
    c = conn.cursor(cursor_factory=DictCursor)
    c.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 100")
    rows = c.fetchall()
    conn.close()
    
    logs = []
    for r in rows:
        l = dict(r)
        l['userId'] = l.pop('userid', None)
        l['sessionId'] = l.pop('sessionid', None)
        l['userAgent'] = l.pop('useragent', None)
        l['data'] = json.loads(l['data']) if l['data'] else {}
        logs.append(l)
    return jsonify(logs)

@app.route('/api/admin/newsletter', methods=['GET'])
@token_required
def admin_get_newsletter():
    conn = get_db()
    c = conn.cursor(cursor_factory=DictCursor)
    c.execute("SELECT * FROM newsletter ORDER BY subscribedat DESC")
    rows = c.fetchall()
    conn.close()
    
    subs = []
    for r in rows:
        s = dict(r)
        s['subscribedAt'] = s.pop('subscribedat', None)
        subs.append(s)
    return jsonify(subs)

@app.route('/api/admin/users', methods=['GET'])
@token_required
def admin_get_users():
    conn = get_db()
    c = conn.cursor(cursor_factory=DictCursor)
    c.execute("SELECT id, email, full_name, phone, address, role, createdat FROM users ORDER BY createdat DESC")
    rows = c.fetchall()
    conn.close()
    
    users = []
    for r in rows:
        u = dict(r)
        # Exclude password
        users.append(u)
    return jsonify(users)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/api/admin/products/upload', methods=['POST'])
@token_required
def upload_product_image():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No selected file'}), 400
    
    if file:
        filename = secure_filename(f"{uuid.uuid4().hex}_{file.filename}")
        file.save(os.path.join(UPLOAD_FOLDER, filename))
        url = f"http://localhost:5000/uploads/{filename}"
        return jsonify({'success': True, 'url': url})

@app.route('/api/admin/products', methods=['POST'])
@token_required
def add_product():
    data = request.json
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO products (name, cat, tag, price, old, imageurl, imageurl_hover, colors, sizes, stock, desc_text, material, rating, ratingcount, combinewith, similar_products, order_num, barcode, has_print)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        ''', (
            data.get('name'), data.get('cat'), data.get('tag'), data.get('price'), data.get('old'),
            data.get('imageUrl'), data.get('imageUrlHover'), json.dumps(data.get('colors', [])), json.dumps(data.get('sizes', [])), json.dumps(data.get('stock', {})),
            data.get('desc'), data.get('material'), data.get('rating', 4.5), data.get('ratingCount', 0),
            json.dumps(data.get('combineWith', [])), json.dumps(data.get('similar', [])), data.get('order_num', 99),
            data.get('barcode'), data.get('has_print', False)
        ))
        new_id = c.fetchone()[0]
        conn.commit()
        return jsonify({'success': True, 'id': new_id})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
    finally:
        conn.close()

@app.route('/api/admin/products/<int:prod_id>', methods=['PUT'])
@token_required
def update_product(prod_id):
    data = request.json
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute('''
            UPDATE products SET
            name=%s, cat=%s, tag=%s, price=%s, old=%s, imageurl=%s, imageurl_hover=%s, colors=%s, sizes=%s, stock=%s, desc_text=%s, material=%s, rating=%s, ratingcount=%s, combinewith=%s, similar_products=%s, order_num=%s, barcode=%s, has_print=%s
            WHERE id=%s
        ''', (
            data.get('name'), data.get('cat'), data.get('tag'), data.get('price'), data.get('old'),
            data.get('imageUrl'), data.get('imageUrlHover'), json.dumps(data.get('colors', [])), json.dumps(data.get('sizes', [])), json.dumps(data.get('stock', {})),
            data.get('desc'), data.get('material'), data.get('rating', 4.5), data.get('ratingCount', 0),
            json.dumps(data.get('combineWith', [])), json.dumps(data.get('similar', [])), data.get('order_num', 99),
            data.get('barcode'), data.get('has_print', False),
            prod_id
        ))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
    finally:
        conn.close()

@app.route('/api/admin/products/<int:prod_id>', methods=['DELETE'])
@token_required
def delete_product(prod_id):
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM products WHERE id=%s", (prod_id,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
    finally:
        conn.close()

@app.route('/api/auth/customer/register', methods=['POST'])
def customer_register():
    data = request.json
    conn = get_db()
    c = conn.cursor()
    try:
        hashed = generate_password_hash(data.get('password'))
        c.execute('''INSERT INTO users (email, password, full_name, role) 
                     VALUES (%s, %s, %s, %s) RETURNING id''', 
                  (data.get('email'), hashed, data.get('full_name'), 'customer'))
        user_id = c.fetchone()[0]
        conn.commit()
        
        token = jwt.encode({'user_id': user_id, 'role': 'customer', 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)}, SECRET_KEY, algorithm="HS256")
        return jsonify({'success': True, 'token': token, 'user': {'id': user_id, 'email': data.get('email'), 'full_name': data.get('full_name')}})
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return jsonify({'success': False, 'message': 'Bu e-posta adresi zaten kullanımda'}), 400
    finally:
        conn.close()

@app.route('/api/auth/customer/login', methods=['POST'])
def customer_login():
    data = request.json
    conn = get_db()
    c = conn.cursor(cursor_factory=DictCursor)
    c.execute("SELECT * FROM users WHERE email=%s AND role='customer'", (data.get('email'),))
    user = c.fetchone()
    conn.close()
    
    if user and check_password_hash(user['password'], data.get('password')):
        token = jwt.encode({'user_id': user['id'], 'role': 'customer', 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)}, SECRET_KEY, algorithm="HS256")
        return jsonify({'success': True, 'token': token, 'user': {'id': user['id'], 'email': user['email'], 'full_name': user['full_name']}})
    return jsonify({'success': False, 'message': 'Geçersiz e-posta veya şifre'}), 401

@app.route('/api/user/profile', methods=['GET', 'PUT'])
def user_profile():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token: return jsonify({'success': False, 'message': 'Token missing'}), 401
    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = decoded['user_id']
    except:
        return jsonify({'success': False, 'message': 'Invalid token'}), 401
        
    conn = get_db()
    c = conn.cursor(cursor_factory=DictCursor)
    
    if request.method == 'GET':
        c.execute("SELECT id, email, full_name, phone, address FROM users WHERE id=%s", (user_id,))
        user = dict(c.fetchone())
        conn.close()
        return jsonify({'success': True, 'profile': user})
        
    if request.method == 'PUT':
        data = request.json
        c.execute("UPDATE users SET full_name=%s, phone=%s, address=%s WHERE id=%s", 
                  (data.get('full_name'), data.get('phone'), data.get('address'), user_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})

@app.route('/api/user/orders', methods=['GET'])
def user_orders():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token: return jsonify({'success': False, 'message': 'Token missing'}), 401
    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = decoded['user_id']
    except:
        return jsonify({'success': False, 'message': 'Invalid token'}), 401
        
    conn = get_db()
    c = conn.cursor(cursor_factory=DictCursor)
    c.execute("SELECT * FROM orders WHERE userid=%s ORDER BY createdat DESC", (str(user_id),))
    rows = c.fetchall()
    conn.close()
    
    orders = []
    for r in rows:
        o = dict(r)
        o['items'] = json.loads(o['items']) if o['items'] else []
        o['createdAt'] = o.pop('createdat', None)
        orders.append(o)
    return jsonify({'success': True, 'orders': orders})

@app.route('/api/user/wishlist', methods=['GET', 'POST', 'DELETE'])
def user_wishlist():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token: return jsonify({'success': False, 'message': 'Token missing'}), 401
    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = decoded['user_id']
    except:
        return jsonify({'success': False, 'message': 'Invalid token'}), 401
        
    conn = get_db()
    c = conn.cursor(cursor_factory=DictCursor)
    
    if request.method == 'GET':
        c.execute('''SELECT p.* FROM products p 
                     JOIN wishlist w ON p.id = w.product_id 
                     WHERE w.user_id = %s''', (user_id,))
        rows = c.fetchall()
        products = []
        for r in rows:
            p = dict(r)
            p['imageUrl'] = p.pop('imageurl', None)
            products.append(p)
        conn.close()
        return jsonify({'success': True, 'wishlist': products})
        
    elif request.method == 'POST':
        data = request.json
        try:
            c.execute("INSERT INTO wishlist (user_id, product_id) VALUES (%s, %s)", (user_id, data.get('product_id')))
            conn.commit()
            return jsonify({'success': True})
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            return jsonify({'success': True})
        finally:
            conn.close()
            
    elif request.method == 'DELETE':
        product_id = request.args.get('product_id')
        c.execute("DELETE FROM wishlist WHERE user_id=%s AND product_id=%s", (user_id, product_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})

@app.route('/api/user/support', methods=['GET', 'POST'])
def user_support():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token: return jsonify({'success': False, 'message': 'Token missing'}), 401
    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = decoded['user_id']
    except:
        return jsonify({'success': False, 'message': 'Invalid token'}), 401
        
    conn = get_db()
    c = conn.cursor(cursor_factory=DictCursor)
    
    if request.method == 'GET':
        c.execute("SELECT * FROM support_tickets WHERE user_id=%s ORDER BY createdat DESC", (user_id,))
        rows = c.fetchall()
        conn.close()
        return jsonify({'success': True, 'tickets': [dict(r) for r in rows]})
        
    if request.method == 'POST':
        data = request.json
        c.execute("INSERT INTO support_tickets (user_id, subject, message) VALUES (%s, %s, %s)",
                  (user_id, data.get('subject'), data.get('message')))
        conn.commit()
        conn.close()
        return jsonify({'success': True})

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
