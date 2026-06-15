import psycopg2
from psycopg2.extras import DictCursor
import json
import os

DB_PARAMS = {
    'dbname': 'vantawear',
    'user': 'postgres',
    'password': '1234',
    'host': 'localhost',
    'port': '5432'
}

SEED_PRODUCTS = [
  {"id":1,"name":"Heavy Oversize Tişört","cat":"Tişört","tag":"Yeni","price":549,"old":None,"imageUrl":"https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?q=80&w=800","emoji":"👕","sizes":json.dumps(["XS","S","M","L","XL"]),"stock":json.dumps({"XS":3,"S":8,"M":15,"L":4,"XL":2}),"desc":"%100 organik pamuk dokuma. Özel yıkama işlemiyle yumuşatılmış, ağır gramajlı oversize kesim. Vanta damgası baskılı ön panel.","material":"Organik pamuk %100. 240gsm ağır gramaj. Soğuk suda yıkayın, düşük ısıda kurutun. Ütü yapmayın.","rating":4.7,"ratingCount":128,"combineWith":json.dumps([2,9,7]),"similar":json.dumps([6,9,3]),"order_num":1},
  {"id":2,"name":"Baggy Straight Jean","cat":"Jean","tag":"Bestseller","price":899,"old":1199,"imageUrl":"https://images.unsplash.com/photo-1542272604-787c3835535d?q=80&w=800","emoji":"👖","sizes":json.dumps(["28","30","32","34"]),"stock":json.dumps({"28":0,"30":6,"32":10,"34":4}),"desc":"Beli ve baldırı geniş, paçası düz kesim. Stone wash işlem görmüş %98 pamuk denim. Vanta metal logo rozeti.","material":"%98 pamuk, %2 elastan. Stone wash işlem. 30°C'de yıkayın, ters çevirerek yıkayın. Çamaşır makinesine uygun.","rating":4.9,"ratingCount":347,"combineWith":json.dumps([1,5,9]),"similar":json.dumps([7,8,4]),"order_num":2},
  {"id":3,"name":"Keten Uzun Gömlek","cat":"Gömlek","tag":"Yeni","price":749,"old":None,"imageUrl":"https://images.unsplash.com/photo-1512436991641-6745cdb1723f?q=80&w=800","emoji":"🧥","sizes":json.dumps(["S","M","L","XL"]),"stock":json.dumps({"S":4,"M":8,"L":5,"XL":1}),"desc":"Yaz için tasarlandı. %100 keten dokuma, oversize kesim. Hafif ve nefes alabilir yapısıyla günlük kullanım için ideal.","material":"%100 keten. Doğal keten rengi. 30°C'de hassas yıkama. Islatarak ütüleyin.","rating":4.5,"ratingCount":89,"combineWith":json.dumps([2,7,4]),"similar":json.dumps([1,6,4]),"order_num":3},
  {"id":4,"name":"Atelier Premium Atlet","cat":"Atlet","tag":"İndirim","price":329,"old":499,"imageUrl":"https://images.unsplash.com/photo-1509942774463-acf339cf87d5?q=80&w=800","emoji":"🩱","sizes":json.dumps(["S","M","L"]),"stock":json.dumps({"S":0,"M":3,"L":7}),"desc":"Vanta Atelier özel üretimi. Ribana kumaş, taş yıkama tekniği. Minimal logo nakışı. Sınırlı adet.","material":"Ribana pamuk %100. Taş yıkama işlemi. Hassas yıkama. Makineyle kurutmayın.","rating":4.6,"ratingCount":62,"combineWith":json.dumps([2,7,8]),"similar":json.dumps([1,6,3]),"order_num":4},
  {"id":5,"name":"Dark Summer Hoodie","cat":"Hoodie","tag":"Bestseller","price":1099,"old":1399,"imageUrl":"https://images.unsplash.com/photo-1556821840-3a63f95609a7?q=80&w=800","emoji":"🖤","sizes":json.dumps(["S","M","L","XL","XXL"]),"stock":json.dumps({"S":2,"M":5,"L":9,"XL":4,"XXL":1}),"desc":"Kalın polar astar, kanguru cep. Oversize fit, düşük omuz. Dark Summer koleksiyonu imzalı parça.","material":"%80 pamuk, %20 polyester. 320gsm polar astar. 30°C'de yıkayın, ters çevirerek. Düşük ısıda kurutun.","rating":4.8,"ratingCount":214,"combineWith":json.dumps([2,8,1]),"similar":json.dumps([8,10]),"order_num":5},
  {"id":6,"name":"Essential Polo Yaka","cat":"Tişört","tag":"Yeni","price":649,"old":None,"imageUrl":"https://images.unsplash.com/photo-1620799140408-edc6dcb6d633?q=80&w=800","emoji":"👔","sizes":json.dumps(["S","M","L","XL"]),"stock":json.dumps({"S":6,"M":12,"L":8,"XL":3}),"desc":"Pique dokuma polo yaka tişört. Slim-oversize arası kesim. Yazlık paletten ilham alan 4 renk seçeneği.","material":"Pique pamuk %100. 200gsm. Soğuk yıkama. Düşük ısıda kurutun.","rating":4.4,"ratingCount":55,"combineWith":json.dumps([2,7,3]),"similar":json.dumps([1,4,3]),"order_num":6},
  {"id":7,"name":"Atelier Keten Şort","cat":"Şort","tag":"Yeni","price":549,"old":None,"imageUrl":"https://images.unsplash.com/photo-1591195853828-11db59a44f6b?q=80&w=800","emoji":"🩳","sizes":json.dumps(["S","M","L","XL"]),"stock":json.dumps({"S":4,"M":9,"L":11,"XL":2}),"desc":"Diz üstü keten şort. Elastik ve ip bağlamalı bel. Atelier koleksiyonunun yaz parçası.","material":"%100 keten. Elastik bel. 30°C hassas yıkama. Kurutucu kullanmayın.","rating":4.5,"ratingCount":43,"combineWith":json.dumps([1,3,4]),"similar":json.dumps([4,8,6]),"order_num":7},
  {"id":8,"name":"Unity Stands Eşofman","cat":"Eşofman","tag":"Limited","price":1799,"old":2199,"imageUrl":"https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?q=80&w=800","emoji":"🏆","sizes":json.dumps(["S","M","L","XL"]),"stock":json.dumps({"S":0,"M":2,"L":4,"XL":1}),"desc":"Unity Stands limited drop kapsamında üretilmiştir. Üst + alt takım, nakış detay, şnur finish. Yalnızca 200 adet.","material":"%80 pamuk, %20 polyester. Özel nakış. 30°C'de yıkayın. Takım olarak yıkayın.","rating":5.0,"ratingCount":38,"combineWith":json.dumps([1,5,9]),"similar":json.dumps([5,10]),"order_num":8},
  {"id":9,"name":"Graphic Oversize Tee","cat":"Tişört","tag":"Bestseller","price":599,"old":799,"imageUrl":"https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?q=80&w=800","emoji":"🎨","sizes":json.dumps(["S","M","L","XL","XXL"]),"stock":json.dumps({"S":3,"M":7,"L":12,"XL":5,"XXL":2}),"desc":"Artık baskı tekniğiyle üretilen grafik ön panel. %100 pamuk, oversize beden. Vanta kültür estetiği.","material":"%100 pamuk. Artık baskı tekniği. Soğuk suda yıkayın. Ters çevirerek yıkayın.","rating":4.7,"ratingCount":183,"combineWith":json.dumps([2,5,8]),"similar":json.dumps([1,6,4]),"order_num":9},
  {"id":10,"name":"Oversize Deri Ceket","cat":"Ceket","tag":"Yeni","price":2599,"old":None,"imageUrl":"https://images.unsplash.com/photo-1551028719-00167b16eac5?q=80&w=800","emoji":"🧥","sizes":json.dumps(["S","M","L","XL"]),"stock":json.dumps({"S":1,"M":4,"L":3,"XL":0}),"desc":"Sentetik deri, tam astar. Oversize fit, metal düğme ve toka detayları. Tüm mevsim kullanılabilir imza parça.","material":"Sentetik deri dış yüzey. Viskon astar. Kuru temizleme önerilir. Direkt güneş ışığından koruyun.","rating":4.8,"ratingCount":72,"combineWith":json.dumps([1,2,9]),"similar":json.dumps([5,8]),"order_num":10},
  {"id":11,"name":"Puffer Şişme Mont","cat":"Mont","tag":"Bestseller","price":3199,"old":3999,"imageUrl":"https://images.unsplash.com/photo-1544441893-675973e31985?q=80&w=800","emoji":"🧥","sizes":json.dumps(["M","L","XL"]),"stock":json.dumps({"M":0,"L":5,"XL":2}),"desc":"Su geçirmez dış yüzey, geri dönüştürülmüş dolgu. Oversize fit.","material":"Su geçirmez nylon dış yüzey. Soğuk makine yıkama.","rating":4.9,"ratingCount":156,"combineWith":json.dumps([1,2,5]),"similar":json.dumps([10,12,8]),"order_num":11},
  {"id":12,"name":"Reflektif Yağmurluk","cat":"Yağmurluk","tag":"İndirim","price":1299,"old":1899,"imageUrl":"https://images.unsplash.com/photo-1539533018447-63fcce2678e3?q=80&w=800","emoji":"🧥","sizes":json.dumps(["S","M","L"]),"stock":json.dumps({"S":4,"M":6,"L":3}),"desc":"Yansıtıcı şerit detaylı yağmurluk. Nefes alan membran kumaş.","material":"Nefes alan membran %100 polyester. Soğuk yıkama.","rating":4.6,"ratingCount":49,"combineWith":json.dumps([1,2,5]),"similar":json.dumps([10,11,8]),"order_num":12}
]

def get_db():
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        conn = psycopg2.connect(db_url)
    else:
        conn = psycopg2.connect(**DB_PARAMS)
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # Products table
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id SERIAL PRIMARY KEY,
        name TEXT,
        cat TEXT,
        tag TEXT,
        price REAL,
        old REAL,
        imageUrl TEXT,
        emoji TEXT,
        sizes TEXT,
        stock TEXT,
        desc_text TEXT,
        material TEXT,
        rating REAL,
        ratingCount INTEGER,
        combineWith TEXT,
        similar_products TEXT,
        order_num INTEGER,
        barcode TEXT,
        has_print BOOLEAN DEFAULT FALSE
    )''')
    
    # Orders table
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id SERIAL PRIMARY KEY,
        sessionId TEXT,
        userId TEXT,
        customerName TEXT,
        address TEXT,
        items TEXT,
        total REAL,
        shipping REAL,
        status TEXT,
        createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Audit Logs
    c.execute('''CREATE TABLE IF NOT EXISTS audit_logs (
        id SERIAL PRIMARY KEY,
        action TEXT,
        data TEXT,
        userId TEXT,
        sessionId TEXT,
        userAgent TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Newsletter
    c.execute('''CREATE TABLE IF NOT EXISTS newsletter (
        id SERIAL PRIMARY KEY,
        email TEXT,
        subscribedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Users
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        email TEXT UNIQUE,
        password TEXT,
        full_name TEXT,
        phone TEXT,
        address TEXT,
        role TEXT,
        createdat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Try adding new columns if users table already existed
    try:
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name TEXT")
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT")
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS address TEXT")
    except Exception:
        pass
        
    # Wishlist
    c.execute('''CREATE TABLE IF NOT EXISTS wishlist (
        id SERIAL PRIMARY KEY,
        user_id INTEGER,
        product_id INTEGER,
        createdat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, product_id)
    )''')
    
    # Support Tickets
    c.execute('''CREATE TABLE IF NOT EXISTS support_tickets (
        id SERIAL PRIMARY KEY,
        user_id INTEGER,
        subject TEXT,
        message TEXT,
        status TEXT DEFAULT 'Açık',
        createdat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Check if products exist
    c.execute('SELECT COUNT(*) FROM products')
    count = c.fetchone()[0]
    if count == 0:
        for p in SEED_PRODUCTS:
            c.execute('''
                INSERT INTO products (id, name, cat, tag, price, old, imageUrl, emoji, sizes, stock, desc_text, material, rating, ratingCount, combineWith, similar_products, order_num)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (p['id'], p['name'], p['cat'], p['tag'], p['price'], p['old'], p['imageUrl'], p['emoji'], json.dumps(p['sizes']), json.dumps(p['stock']), p['desc'], p['material'], p['rating'], p['ratingCount'], json.dumps(p['combineWith']), json.dumps(p['similar']), p['order_num']))
            
    conn.commit()
    cursor = conn.cursor()
    # Reset sequence so auto-increment works for new inserts (PostgreSQL specific)
    try:
        cursor.execute("SELECT setval('products_id_seq', (SELECT MAX(id) FROM products))")
        conn.commit()
    except Exception:
        pass
    
    conn.close()

if __name__ == '__main__':
    init_db()
    print("PostgreSQL Database initialized successfully.")
