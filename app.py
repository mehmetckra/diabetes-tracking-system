from flask import Flask, render_template, redirect, url_for, request, jsonify
import os
import mysql.connector

app = Flask(__name__,
            template_folder=os.path.abspath('templates'),
            static_folder=os.path.abspath('static'))

# MySQL bağlantı yapılandırması
db_config = {
    'host': 'localhost',
    'user': 'root',  # MySQL kullanıcı adınız
    'password': '351872',  # MySQL şifreniz
    'database': 'diabettakip',
    'port': 3307
}

# Veritabanı bağlantı fonksiyonu
def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as err:
        print(f"Veritabanı bağlantı hatası: {err}")
        return None

# Ana sayfa route'u
@app.route('/')
def index():
    return render_template('login.html')

@app.route('/hasta-giris', methods=['GET', 'POST'])
def hasta_giris():
    if request.method == 'POST':
        hasta_id = request.form.get('hasta_id')
        ad = request.form.get('ad').strip()
        
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT * FROM hasta 
                    WHERE hasta_id = %s 
                    AND TRIM(ad) = %s
                """, (hasta_id, ad))
                hasta = cursor.fetchone()
                
                if hasta:
                    return redirect(url_for('hasta_panel', hasta_id=hasta_id))
                else:
                    return "Hasta bilgileri bulunamadı!"
                    
            except mysql.connector.Error as err:
                return f"Bir hata oluştu: {err}"
            finally:
                cursor.close()
                conn.close()
                
    return render_template('login.html')

@app.route('/doktor-giris', methods=['GET', 'POST'])
def doktor_giris():
    if request.method == 'POST':
        doktor_id = request.form.get('doktor_id')
        doktor_ad = request.form.get('doktor_ad')
        
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)
                # Doktor kontrolü
                cursor.execute("SELECT * FROM doktor WHERE doktor_id = %s AND ad = %s", 
                             (doktor_id, doktor_ad))
                doktor = cursor.fetchone()
                
                if doktor:
                    return redirect(url_for('doktor_panel', doktor_id=doktor_id))
                else:
                    return "Doktor bilgileri bulunamadı!"
            except mysql.connector.Error as err:
                return f"Bir hata oluştu: {err}"
            finally:
                cursor.close()
                conn.close()
    return render_template('login.html')

@app.route('/doktor-panel/<int:doktor_id>')
def doktor_panel(doktor_id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            # Doktor bilgilerini al
            cursor.execute("SELECT ad FROM doktor WHERE doktor_id = %s", (doktor_id,))
            doktor = cursor.fetchone()
            
            # Randevu ve bekleyen sonuç sayısını al
            randevu_sayisi = 5  # Örnek veri, veritabanından alınacak
            bekleyen_sonuc = 3  # Örnek veri, veritabanından alınacak
            
            return render_template('doktor_panel.html', 
                                   doktor=doktor,
                                   randevu_sayisi=randevu_sayisi,
                                   bekleyen_sonuc=bekleyen_sonuc)
        except mysql.connector.Error as err:
            return f"Bir hata oluştu: {err}"
        finally:
            cursor.close()
            conn.close()
    return "Veritabanı bağlantı hatası!"

@app.route('/lab-sonuclari')
def lab_sonuclari():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            # Filtreleme parametrelerini al
            hasta_id = request.args.get('hasta_id')
            tur = request.args.get('tur')
            
            # Tüm hastaları getir (filtreleme için)
            cursor.execute("""
                SELECT hasta_id, CONCAT(ad, ' ', soyad) as ad_soyad
                FROM hasta
                ORDER BY ad, soyad
            """)
            hastalar = cursor.fetchall()
            
            # Sonuçları getir
            query = """
                SELECT 
                    l.sonuç_id as sonuc_id,
                    l.hasta_id,
                    CONCAT(h.ad, ' ', h.soyad) as hasta_adi,
                    l.tür as tur,
                    DATE_FORMAT(l.tarih, '%d/%m/%Y') as tarih
                FROM laboratuvar_sonucu l
                JOIN hasta h ON l.hasta_id = h.hasta_id
                WHERE 1=1
            """
            params = []
            
            if hasta_id:
                query += " AND l.hasta_id = %s"
                params.append(hasta_id)
            if tur:
                query += " AND l.tür = %s"
                params.append(tur)
                
            query += " ORDER BY l.tarih DESC"
            
            cursor.execute(query, params)
            sonuclar = cursor.fetchall()
            
            return render_template('lab_sonuclari.html',
                                hastalar=hastalar,
                                sonuclar=sonuclar)
                                
        except mysql.connector.Error as err:
            return f"Bir hata oluştu: {err}"
        finally:
            cursor.close()
            conn.close()
            
    return "Veritabanı bağlantı hatası!"

@app.route('/get-dozaj/<int:ilac_id>')
def get_dozaj(ilac_id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT dozaj, isim FROM ilac WHERE ilac_id = %s", (ilac_id,))
            ilac = cursor.fetchone()
            
            # İlacın insülin olup olmadığını kontrol et
            is_insulin = 'insülin' in ilac['isim'].lower() if ilac else False
            
            # Dozaj verilerini liste olarak döndür
            dozajlar = [ilac['dozaj']] if ilac else []
            
            return jsonify({
                'dozajlar': dozajlar,
                'is_insulin': is_insulin
            })
            
        except mysql.connector.Error as err:
            return jsonify({'error': str(err)}), 500
        finally:
            cursor.close()
            conn.close()
    return jsonify({'error': 'Database connection error'}), 500

@app.route('/get-insulin-details/<int:ilac_id>/<tip>')
def get_insulin_details(ilac_id, tip):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            # İnsülin tipine göre sorgu
            if tip == 'kisa':
                cursor.execute("""
                    SELECT id, bilgi 
                    FROM insulin_detaylari 
                    WHERE ilac_id = %s AND tip = 'kisa_etkili'
                """, (ilac_id,))
            else:
                cursor.execute("""
                    SELECT id, bilgi 
                    FROM insulin_detaylari 
                    WHERE ilac_id = %s AND tip = 'uzun_etkili'
                """, (ilac_id,))
                
            details = cursor.fetchall()
            return jsonify({'details': details})
            
        except mysql.connector.Error as err:
            return jsonify({'error': str(err)}), 500
        finally:
            cursor.close()
            conn.close()
    return jsonify({'error': 'Database connection error'}), 500

@app.route('/get-alt-ilaclar/<int:ilac_id>')
def get_alt_ilaclar(ilac_id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            # İlacın türüne göre alt ilaçları getir
            cursor.execute("SELECT id, isim FROM alt_ilaclar WHERE ilac_id = %s", (ilac_id,))
            alt_ilaclar = cursor.fetchall()
            return jsonify(alt_ilaclar)
        except mysql.connector.Error as err:
            return jsonify({'error': str(err)}), 500
        finally:
            cursor.close()
            conn.close()
    return jsonify({'error': 'Database connection error'}), 500

@app.route('/get-insulin-list/<tip>')
def get_insulin_list(tip):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            if tip == 'kisa':
                cursor.execute("""
                    SELECT ilac_id as id, isim, kisa_etkili_insulin as dozaj
                    FROM ilac 
                    WHERE kisa_etkili_insulin IS NOT NULL
                """)
            else:
                cursor.execute("""
                    SELECT ilac_id as id, isim, uzun_etkili_insulin as dozaj
                    FROM ilac 
                    WHERE uzun_etkili_insulin IS NOT NULL
                """)
            
            insulinler = cursor.fetchall()
            print(f"Bulunan insülinler: {insulinler}")  # Debug için
            return jsonify({'insulinler': insulinler})
            
        except mysql.connector.Error as err:
            print(f"Veritabanı hatası: {err}")
            return jsonify({'error': str(err)}), 500
        finally:
            cursor.close()
            conn.close()
            
    return jsonify({'error': 'Veritabanı bağlantı hatası'}), 500

@app.route('/get-insulin-dosage-info/<tip>/<int:ilac_id>')  # Route adını değiştirdik
def get_insulin_dosage_info(tip, ilac_id):  # Fonksiyon adını değiştirdik
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            # İnsülin tipine göre dozaj sorgusu
            if tip == 'kisa':
                sql = "SELECT kısa_etkili_insilün as dozaj FROM ilac WHERE ilac_id = %s"
            else:
                sql = "SELECT uzun_etkili_insilün as dozaj FROM ilac WHERE ilac_id = %s"
            
            cursor.execute(sql, (ilac_id,))
            result = cursor.fetchone()
            
            if result and result['dozaj']:
                dozajlar = [result['dozaj']] if not isinstance(result['dozaj'], list) else result['dozaj']
            else:
                dozajlar = []
                
            return jsonify({'dozajlar': dozajlar})
            
        except mysql.connector.Error as err:
            print(f"Veritabanı hatası: {err}")
            return jsonify({'error': str(err)}), 500
        finally:
            cursor.close()
            conn.close()
            
    return jsonify({'error': 'Veritabanı bağlantı hatası'}), 500

@app.route('/get-hap-list')
def get_hap_list():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            # Sadece hap_ismi olan ilaçları getir
            cursor.execute("""
                SELECT ilac_id, hap_ismi 
                FROM ilac 
                WHERE hap_ismi IS NOT NULL 
                AND hap_ismi != ''
            """)
            haplar = cursor.fetchall()
            return jsonify(haplar)
        except mysql.connector.Error as err:
            return jsonify({'error': str(err)}), 500
        finally:
            cursor.close()
            conn.close()
    return jsonify({'error': 'Veritabanı bağlantı hatası'})

@app.route('/ilac-recete', methods=['GET', 'POST'])  # 'ilaç-recete' yerine 'ilac-recete' kullanıyoruz
def ilac_recete():  # 'ilaç_recete' yerine 'ilac_recete' kullanıyoruz
    if request.method == 'POST':
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)
                
                # Form verilerini al
                hasta_id = request.form.get('hasta_id')
                ilac_id = request.form.get('specific_ilac')  # İlaç ID'sini specific_ilac'tan al
                dozaj_miktar = request.form.get('dozaj_miktar')
                dozaj_birim = request.form.get('dozaj_birim')
                aciklama = request.form.get('aciklama', '')
                
                # Dozaj bilgisini açıklamaya ekle
                tam_aciklama = f"Dozaj: {dozaj_miktar} {dozaj_birim}\n{aciklama}"
                
                if not hasta_id or not ilac_id:
                    return jsonify({'error': 'Hasta ID ve İlaç seçimi zorunludur'}), 400
                
                # Reçeteyi kaydet
                cursor.execute("""
                    INSERT INTO reçete (
                        hastaid,
                        ilac_id,
                        dozaj_miktar,
                        dozaj_birim,
                        tarih,
                        aciklama
                    ) VALUES (%s, %s, %s, %s, NOW(), %s)
                """, (hasta_id, ilac_id, dozaj_miktar, dozaj_birim, tam_aciklama))
                
                conn.commit()
                recete_id = cursor.lastrowid
                
                # Reçete detaylarını al
                cursor.execute("""
                    SELECT reçete_id, DATE_FORMAT(tarih, '%d/%m/%Y %H:%i') as tarih
                    FROM reçete
                    WHERE reçete_id = %s
                """, (recete_id,))
                
                recete = cursor.fetchone()
                
                return jsonify({
                    'success': True,
                    'recete_id': recete['reçete_id'],
                    'tarih': recete['tarih']
                })
                
            except mysql.connector.Error as err:
                print(f"Veritabanı hatası: {err}")
                return jsonify({'error': str(err)}), 500
            finally:
                cursor.close()
                conn.close()
    
    return render_template('ilac_recete.html', doktor={'ad': 'Mehmet Öz'})

@app.route('/randevu')
def randevu():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            # Tüm randevuları getir (r.saati yerine r.saat kullanıldı)
            cursor.execute("""
                SELECT r.randevu_id, r.hasta_id,
                       CONCAT(h.ad, ' ', h.soyad) as hasta_adi,
                       DATE_FORMAT(r.tarih, '%d/%m/%Y') as tarih,
                       DATE_FORMAT(r.saat, '%H:%i') as saat,
                       r.doktor_id
                FROM randevu r
                JOIN hasta h ON r.hasta_id = h.hasta_id
                WHERE r.tarih >= CURDATE()
                ORDER BY r.tarih, r.saat
            """)
            randevular = cursor.fetchall()
            return render_template('randevu_panel.html', randevular=randevular)
        except mysql.connector.Error as err:
            return f"Bir hata oluştu: {err}"
        finally:
            cursor.close()
            conn.close()
    return "Veritabanı bağlantı hatası!"

@app.route('/randevu/filter')
def filter_randevular():
    tarih = request.args.get('tarih')
    siralama = request.args.get('siralama')
    
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            base_query = """
                SELECT r.randevu_id, r.hasta_id,
                       CONCAT(h.ad, ' ', h.soyad) as hasta_adi,
                       DATE_FORMAT(r.tarih, '%d/%m/%Y') as tarih,
                       DATE_FORMAT(r.saat, '%H:%i') as saat,
                       r.doktor_id
                FROM randevu r
                JOIN hasta h ON r.hasta_id = h.hasta_id
                WHERE 1=1
            """
            
            params = []
            
            if tarih:
                base_query += " AND r.tarih = %s"
                params.append(tarih)
            
            if siralama == 'tarih':
                base_query += " ORDER BY r.tarih, r.saat"
            elif siralama == 'hasta':
                base_query += " ORDER BY h.ad, h.soyad"
            
            cursor.execute(base_query, params)
            randevular = cursor.fetchall()
            
            return jsonify({'success': True, 'randevular': randevular})
            
        except mysql.connector.Error as err:
            return jsonify({'success': False, 'error': str(err)}), 500
        finally:
            cursor.close()
            conn.close()
            
    return jsonify({'success': False, 'error': 'Veritabanı bağlantı hatası'}), 500

@app.route('/randevu/guncelle/<int:randevu_id>', methods=['POST'])
def randevu_guncelle(randevu_id):
    durum = request.form.get('durum')
    
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE randevu
                SET durum = %s
                WHERE randevu_id = %s
            """, (durum, randevu_id))
            conn.commit()
            return jsonify({'success': True})
        except mysql.connector.Error as err:
            return jsonify({'success': False, 'error': str(err)}), 500
        finally:
            cursor.close()
            conn.close()
            
    return jsonify({'success': False, 'error': 'Veritabanı bağlantı hatası'}), 500

@app.route('/get-insulin-selection/<tip>')
def get_insulin_selection(tip):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            if tip == 'kisa':
                sql = """
                    SELECT ilac_id, isim, kısa_etkili_insilün as dozaj
                    FROM ilac 
                    WHERE kısa_etkili_insilün IS NOT NULL
                    AND kısa_etkili_insilün != ''
                """
            else:
                sql = """
                    SELECT ilac_id, isim, uzun_etkili_insilün as dozaj
                    FROM ilac 
                    WHERE uzun_etkili_insilün IS NOT NULL
                    AND uzun_etkili_insilün != ''
                """
            
            print(f"SQL Sorgusu: {sql}")  # Debug için
            cursor.execute(sql)
            ilaclar = cursor.fetchall()
            print(f"Bulunan ilaçlar: {ilaclar}")  # Debug için
            
            return jsonify({'ilaclar': ilaclar})
            
        except mysql.connector.Error as err:
            print(f"Veritabanı hatası: {err}")
            return jsonify({'error': str(err)}), 500
        finally:
            cursor.close()
            conn.close()
    return jsonify({'error': 'Veritabanı bağlantı hatası'})

@app.route('/hasta-panel/<int:hasta_id>')
def hasta_panel(hasta_id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            # Hasta bilgilerini al
            cursor.execute("""
                SELECT hasta_id, CONCAT(ad, ' ', soyad) as ad_soyad, 
                       DATE_FORMAT(doğum_tarihi, '%d/%m/%Y') as dogum_tarihi
                FROM hasta 
                WHERE hasta_id = %s
            """, (hasta_id,))
            hasta = cursor.fetchone()
            
            try:
                # Yaklaşan randevuyu al
                cursor.execute("""
                    SELECT randevu_id, 
                           DATE_FORMAT(tarih, '%d/%m/%Y') as tarih,
                           DATE_FORMAT(saati, '%H:%i') as saat
                    FROM randevu
                    WHERE tarih >= CURDATE()
                    ORDER BY tarih, saati LIMIT 1
                """)
                yaklasan_randevu = cursor.fetchone()
            except mysql.connector.Error:
                yaklasan_randevu = None

            try:
                # Son reçeteyi al
                cursor.execute("""
                    SELECT reçete_id, DATE_FORMAT(tarih, '%d/%m/%Y') as tarih
                    FROM reçete
                    ORDER BY tarih DESC LIMIT 1
                """)
                son_recete = cursor.fetchone()
            except mysql.connector.Error:
                son_recete = None

            try:
                # Son lab sonucunu al
                cursor.execute("""
                    SELECT sonuç_id, DATE_FORMAT(tarih, '%Y-%m-%d') as tarih, tür
                    FROM laboratuvar_sonucu 
                    ORDER BY tarih DESC LIMIT 1
                """)
                son_lab = cursor.fetchone()
            except mysql.connector.Error:
                son_lab = None
            
            return render_template('hasta_panel.html',
                                hasta=hasta,
                                yaklasan_randevu=yaklasan_randevu,
                                son_recete=son_recete,
                                son_lab=son_lab)
                                
        except mysql.connector.Error as err:
            return f"Bir hata oluştu: {err}"
        finally:
            cursor.close()
            conn.close()
    
    return "Veritabanı bağlantı hatası!"

@app.route('/hasta-beslenme/<int:hasta_id>')
def hasta_beslenme(hasta_id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT 
                    plan_id,
                    DATE_FORMAT(baslangic_tarihi, '%d/%m/%Y') as baslangic_tarihi,
                    DATE_FORMAT(bitis_tarihi, '%d/%m/%Y') as bitis_tarihi,
                    aciklama
                FROM beslenme_plani
                WHERE hasta_id = %s
                ORDER BY baslangic_tarihi DESC
            """, (hasta_id,))
            beslenme_planlari = cursor.fetchall()
            
            return render_template('hasta_beslenme.html', 
                                hasta_id=hasta_id,
                                beslenme_planlari=beslenme_planlari)
        except mysql.connector.Error as err:
            return f"Bir hata oluştu: {err}"
        finally:
            cursor.close()
            conn.close()
    return "Veritabanı bağlantı hatası!"

@app.route('/hasta-egzersiz/<int:hasta_id>')
def hasta_egzersiz(hasta_id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT 
                    egzersiz_id,
                    DATE_FORMAT(tarih, '%d/%m/%Y') as tarih,
                    DATE_FORMAT(süre, '%H:%i') as sure,
                    tür as tur,
                    notlar
                FROM egzersiz
                WHERE hasta_id = %s
                ORDER BY tarih DESC, süre DESC
            """, (hasta_id,))
            egzersizler = cursor.fetchall()
            
            return render_template('hasta_egzersiz.html', 
                                hasta_id=hasta_id,
                                egzersizler=egzersizler)
        except mysql.connector.Error as err:
            return f"Bir hata oluştu: {err}"
        finally:
            cursor.close()
            conn.close()
    return "Veritabanı bağlantı hatası!"

@app.route('/hasta-lab-sonuclari/<int:hasta_id>')
def hasta_lab_sonuclari(hasta_id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT 
                    sonuç_id as sonuc_id,
                    DATE_FORMAT(tarih, '%d/%m/%Y') as tarih,
                    tür as tur
                FROM laboratuvar_sonucu 
                WHERE hasta_id = %s
                ORDER BY tarih DESC
            """, (hasta_id,))
            sonuclar = cursor.fetchall()
            
            return render_template('hasta_lab_sonuclari.html', 
                                hasta_id=hasta_id,
                                sonuclar=sonuclar)
        except mysql.connector.Error as err:
            return f"Bir hata oluştu: {err}"
        finally:
            cursor.close()
            conn.close()
    return "Veritabanı bağlantı hatası!"

@app.route('/hasta-randevu/<int:hasta_id>', methods=['GET', 'POST'])
def hasta_randevu(hasta_id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            if request.method == 'POST':
                doktor_id = request.form.get('doktor_id')
                tarih = request.form.get('tarih')
                saat = request.form.get('saat')
                
                # Aynı gün için randevu kontrolü
                cursor.execute("""
                    SELECT COUNT(*) as randevu_sayisi
                    FROM randevu
                    WHERE hasta_id = %s AND tarih = %s
                """, (hasta_id, tarih))
                
                result = cursor.fetchone()
                if result['randevu_sayisi'] > 0:
                    return jsonify({
                        'success': False,
                        'error': 'Aynı gün için zaten bir randevunuz bulunmaktadır!'
                    })
                
                # Randevuyu kaydet
                cursor.execute("""
                    INSERT INTO randevu (hasta_id, doktor_id, tarih, saat)
                    VALUES (%s, %s, %s, %s)
                """, (hasta_id, doktor_id, tarih, saat))
                
                conn.commit()
                return jsonify({'success': True})
            
            # Doktorları getir (diyetisyen bilgisiyle birlikte)
            cursor.execute("""
                SELECT 
                    d.doktor_id,
                    d.ad,
                    d.soyad,
                    d.uzmanlık,
                    CASE WHEN dy.diyetisyen_id IS NOT NULL THEN TRUE ELSE FALSE END as is_diyetisyen
                FROM doktor d
                LEFT JOIN diyetisyen dy ON d.doktor_id = dy.diyetisyen_id
                ORDER BY d.ad, d.soyad
            """)
            doktorlar = cursor.fetchall()
            
            # Müsait saatleri getir (örnek)
            musait_saatler = [
                '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
                '13:00', '13:30', '14:00', '14:30', '15:00', '15:30'
            ]
            
            # Mevcut randevuları getir
            cursor.execute("""
                SELECT 
                    r.randevu_id,
                    CONCAT(d.ad, ' ', d.soyad) as doktor_adi,
                    DATE_FORMAT(r.tarih, '%d/%m/%Y') as tarih,
                    DATE_FORMAT(r.saat, '%H:%i') as saat
                FROM randevu r
                JOIN doktor d ON r.doktor_id = d.doktor_id
                WHERE r.hasta_id = %s AND r.tarih >= CURDATE()
                ORDER BY r.tarih, r.saat
            """, (hasta_id,))
            mevcut_randevular = cursor.fetchall()
            
            from datetime import date
            min_tarih = date.today().strftime('%Y-%m-%d')
            
            return render_template('hasta_randevu.html',
                                hasta_id=hasta_id,
                                doktorlar=doktorlar,
                                musait_saatler=musait_saatler,
                                mevcut_randevular=mevcut_randevular,
                                min_tarih=min_tarih)
                                
        except mysql.connector.Error as err:
            return f"Bir hata oluştu: {err}"
        finally:
            cursor.close()
            conn.close()
            
    return "Veritabanı bağlantı hatası!"

@app.route('/hasta-receteler/<int:hasta_id>')
def hasta_receteler(hasta_id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            # Hasta bilgilerini al
            cursor.execute("""
                SELECT CONCAT(ad, ' ', soyad) as ad_soyad
                FROM hasta 
                WHERE hasta_id = %s
            """, (hasta_id,))
            hasta = cursor.fetchone()
            
            if not hasta:
                return "Hasta bilgileri bulunamadı!", 404
            
            # Reçeteleri al
            cursor.execute("""
                SELECT 
                    reçete_id as recete_id,
                    DATE_FORMAT(tarih, '%d/%m/%Y') as tarih,
                    ilac_ismi,
                    ilac_turu,
                    dozaj,
                    aciklama
                FROM reçete
                WHERE hasta_id = %s
                ORDER BY tarih DESC
            """, (hasta_id,))
            receteler = cursor.fetchall()
            
            return render_template('hasta_receteler.html', 
                                hasta_id=hasta_id,
                                hasta=hasta,
                                receteler=receteler)
        except mysql.connector.Error as err:
            return f"Bir hata oluştu: {err}"
        finally:
            cursor.close()
            conn.close()
    return "Veritabanı bağlantı hatası!"

@app.route('/get-specific-ilaclar/<tip>')
def get_specific_ilaclar(tip):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            if tip == 'kisa':
                sql = """
                    SELECT ilac_id, isim, kısa_etkili_insülin as dozaj
                    FROM ilac 
                    WHERE kısa_etkili_insülin IS NOT NULL
                    AND kısa_etkili_insülin != ''
                """
            elif tip == 'uzun':
                sql = """
                    SELECT ilac_id, isim, uzun_etkili_insülin as dozaj
                    FROM ilac 
                    WHERE uzun_etkili_insülin IS NOT NULL
                    AND uzun_etkili_insülin != ''
                """
            else:  # hap
                sql = """
                    SELECT ilac_id, isim, hap_ismi as dozaj
                    FROM ilac 
                    WHERE hap_ismi IS NOT NULL
                    AND hap_ismi != ''
                """
            
            cursor.execute(sql)
            ilaclar = cursor.fetchall()
            return jsonify({'ilaclar': ilaclar})
            
        except mysql.connector.Error as err:
            return jsonify({'error': str(err)}), 500
        finally:
            cursor.close()
            conn.close()
    return jsonify({'error': 'Veritabanı bağlantı hatası'})

@app.route('/beslenme-plani-olustur', methods=['GET', 'POST'])
def beslenme_plani_olustur():
    if request.method == 'POST':
        baslangic_tarihi = request.form.get('baslangic_tarihi')
        bitis_tarihi = request.form.get('bitis_tarihi')
        hasta_id = request.form.get('hasta_id')
        
        # Öğün seçimlerini al
        kahvalti = request.form.getlist('kahvalti')
        ogle_yemegi = request.form.getlist('ogle_yemegi')
        aksam_yemegi = request.form.getlist('aksam_yemegi')
        
        # Açıklama alanını oluştur
        aciklama = f"""
Kahvaltı:
{chr(10).join(kahvalti)}

Öğle Yemeği:
{chr(10).join(ogle_yemegi)}

Akşam Yemeği:
{chr(10).join(aksam_yemegi)}
"""
        
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO beslenme_plani 
                    (baslangic_tarihi, bitis_tarihi, aciklama, hasta_id)
                    VALUES (%s, %s, %s, %s)
                """, (baslangic_tarihi, bitis_tarihi, aciklama, hasta_id))
                conn.commit()
                
                return jsonify({'success': True, 'message': 'Beslenme planı başarıyla oluşturuldu'})
            except mysql.connector.Error as err:
                return jsonify({'success': False, 'error': str(err)})
            finally:
                cursor.close()
                conn.close()
                
    # GET isteği için hastaları getir
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT hasta_id, CONCAT(ad, ' ', soyad) as ad_soyad FROM hasta")
            hastalar = cursor.fetchall()
            return render_template('beslenme_plani_olustur.html', hastalar=hastalar)
        except mysql.connector.Error as err:
            return f"Bir hata oluştu: {err}"
        finally:
            cursor.close()
            conn.close()
            
    return render_template('beslenme_plani_olustur.html')

@app.route('/egzersiz-plani-olustur', methods=['GET', 'POST'])
def egzersiz_plani_olustur():
    if request.method == 'POST':
        hasta_id = request.form.get('hasta_id')
        tur = request.form.get('tur')
        sure = request.form.get('sure')
        tarih = request.form.get('tarih')
        notlar = request.form.get('notlar')
        
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO egzersiz 
                    (hasta_id, tür, süre, tarih, notlar)
                    VALUES (%s, %s, %s, %s, %s)
                """, (hasta_id, tur, sure, tarih, notlar))
                conn.commit()
                return jsonify({'success': True})
            except mysql.connector.Error as err:
                return jsonify({'success': False, 'error': str(err)})
            finally:
                cursor.close()
                conn.close()
    
    # GET isteği için hastaları getir
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT hasta_id, CONCAT(ad, ' ', soyad) as ad_soyad FROM hasta")
            hastalar = cursor.fetchall()
            return render_template('egzersiz_plani_olustur.html', hastalar=hastalar)
        except mysql.connector.Error as err:
            return f"Bir hata oluştu: {err}"
        finally:
            cursor.close()
            conn.close()
    
    return render_template('egzersiz_plani_olustur.html')

@app.route('/randevu/iptal/<int:randevu_id>', methods=['POST'])
def randevu_iptal(randevu_id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            # Önce randevunun gelecek tarihli olduğunu kontrol et
            cursor.execute("""
                SELECT tarih 
                FROM randevu 
                WHERE randevu_id = %s 
                AND tarih >= CURDATE()
            """, (randevu_id,))
            
            randevu = cursor.fetchone()
            
            if not randevu:
                return jsonify({
                    'success': False,
                    'error': 'Geçmiş randevular iptal edilemez.'
                }), 400
            
            # Randevuyu sil
            cursor.execute("DELETE FROM randevu WHERE randevu_id = %s", (randevu_id,))
            conn.commit()
            
            return jsonify({'success': True})
            
        except mysql.connector.Error as err:
            return jsonify({
                'success': False,
                'error': str(err)
            }), 500
        finally:
            cursor.close()
            conn.close()
            
    return jsonify({
        'success': False,
        'error': 'Veritabanı bağlantı hatası'
    }), 500

if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
