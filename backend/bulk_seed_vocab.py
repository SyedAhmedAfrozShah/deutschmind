import os
import sqlite3
import json
import asyncio
import random
from typing import List, Dict, Any
from backend.models import get_db_connection, init_goethe_vocab_schema
from backend.translator import batch_translate_vocab
from backend.export_static_data import export_sqlite_to_static_json

# =========================================================================
# COMPREHENSIVE GOETHE-INSTITUT CEFR VOCABULARY BLUEPRINT DATASETS
# =========================================================================

VOCAB_DATASETS = {
    "ZERO": [
        ("Hallo", "Hello", "ہیلو / سلام"), ("Tschüss", "Bye", "خدا حافظ"),
        ("Guten Morgen", "Good morning", "صبح بخیر"), ("Guten Tag", "Good day / Hello", "دن بخیر"),
        ("Guten Abend", "Good evening", "شام بخیر"), ("Gute Nacht", "Good night", "شب بخیر"),
        ("Ja", "Yes", "جی ہاں"), ("Nein", "No", "نہیں"),
        ("Danke", "Thank you", "شکریہ"), ("Danke schön", "Thank you very much", "بہت بہت شکریہ"),
        ("Bitte", "Please / You're welcome", "برائے مہربانی / خوش آمدید"), ("Entschuldigung", "Excuse me / Sorry", "معاف کیجیے گا"),
        ("Auf Wiedersehen", "Goodbye (formal)", "الوداع"), ("Wie geht's?", "How are you?", "آپ کا کیا حال ہے؟"),
        ("Gut", "Good", "اچھا"), ("Sehr gut", "Very good", "بہت اچھا"),
        ("Eins", "One", "ایک"), ("Zwei", "Two", "دو"), ("Drei", "Three", "تین"),
        ("Vier", "Four", "چار"), ("Fünf", "Five", "پانچ"), ("Sechs", "Six", "چھ"),
        ("Sieben", "Seven", "سات"), ("Acht", "Eight", "آٹھ"), ("Neun", "Nine", "نو"), ("Zehn", "Ten", "دس"),
        ("Montag", "Monday", "پیر"), ("Dienstag", "Tuesday", "منگل"), ("Mittwoch", "Wednesday", "بدھ"),
        ("Donnerstag", "Thursday", "جمعرات"), ("Freitag", "Friday", "جمعہ"), ("Samstag", "Saturday", "ہفتہ"), ("Sonntag", "Sunday", "اتوار"),
        ("das Wasser", "water", "پانی"), ("der Tee", "tea", "چائے"), ("der Kaffee", "coffee", "کافی"),
        ("das Brot", "bread", "روٹی / بریڈ"), ("die Milch", "milk", "دھودھ"),
        ("Herr", "Mr. / Sir", "محترم"), ("Frau", "Mrs. / Ms. / Woman", "محترمہ / خاتون"),
        ("Wer?", "Who?", "کون؟"), ("Was?", "What?", "کیا؟"), ("Wo?", "Where?", "کہاں؟"),
        ("Wie?", "How?", "کیسے؟"), ("Warum?", "Why?", "کیوں؟"),
        ("Ich", "I", "میں"), ("Du", "You (informal)", "تم"), ("Sie", "You (formal)", "آپ"),
        ("Wir", "We", "ہم")
    ],
    "A1": [
        ("der Apfel", "apple", "سیب"), ("die Banane", "banana", "کیلا"), ("das Ei", "egg", "انڈا"),
        ("der Fisch", "fish", "مچھلی"), ("das Fleisch", "meat", "گوشت"), ("der Käse", "cheese", "پنیر"),
        ("die Butter", "butter", "مکھن"), ("der Zucker", "sugar", "چینی"), ("das Salz", "salt", "نمک"),
        ("der Reis", "rice", "چاول"), ("die Suppe", "soup", "سープ"), ("der Saft", "juice", "رس / جوس"),
        ("das Bier", "beer", "بیئر"), ("der Wein", "wine", "شراب"), ("das Gericht", "dish / meal", "کھانا"),
        ("der Hunger", "hunger", "بھوک"), ("der Durst", "thirst", "پیاس"),
        ("der Bahnhof", "train station", "ریلوے اسٹیشن"), ("der Flughafen", "airport", "ہوائی اڈہ"),
        ("die Haltestelle", "bus/tram stop", "بس اسٹاپ"), ("die Fahrkarte", "ticket", "ٹکٹ"),
        ("der Zug", "train", "ٹرین"), ("der Bus", "bus", "بس"), ("das Flugzeug", "airplane", "جہاز"),
        ("das Taxi", "taxi", "ٹیکسی"), ("das Fahrrad", "bicycle", "سائیکل"), ("das Auto", "car", "گاڑی"),
        ("die Straße", "street / road", "سڑک"), ("der Platz", "square / seat", "چوک / جگہ"),
        ("die Stadt", "city / town", "شہر"), ("das Land", "country / countryside", "ملک / دیہات"),
        ("das Haus", "house", "گھر"), ("die Wohnung", "apartment", "فلیٹ"), ("das Zimmer", "room", "کمرہ"),
        ("die Küche", "kitchen", "باورچی خانہ"), ("das Bad", "bathroom", "غسل خانہ"),
        ("das Bett", "bed", "بستر"), ("der Tisch", "table", "میز"), ("der Stuhl", "chair", "کرسی"),
        ("der Schrank", "cupboard / wardrobe", "الماری"), ("die Tür", "door", "دروازہ"),
        ("das Fenster", "window", "کھڑکی"), ("der Schlüssel", "key", "چابی"),
        ("der Vater", "father", "والد"), ("die Mutter", "mother", "والدہ"), ("der Sohn", "son", "بیٹا"),
        ("die Tochter", "daughter", "بیٹی"), ("der Bruder", "brother", "بھائی"), ("die Schwester", "sister", "بہن"),
        ("die Familie", "family", "خاندان"), ("der Freund", "friend (male)", "دوست"),
        ("die Freundin", "friend (female)", "سہیلی"), ("das Kind", "child", "بچہ"),
        ("der Mann", "man / husband", "آدمی / شوہر"), ("die Frau", "woman / wife", "عورت / بیوی"),
        ("die Arbeit", "work / job", "کام / ملازمت"), ("der Beruf", "profession", "پیشہ"),
        ("der Arzt", "doctor (male)", "ڈاکٹر"), ("die Ärztin", "doctor (female)", "لیڈی ڈاکٹر"),
        ("der Lehrer", "teacher (male)", "استاد"), ("die Lehrerin", "teacher (female)", "استانی"),
        ("der Student", "student (male)", "طالب علم"), ("die Studentin", "student (female)", "طالبہ"),
        ("die Schule", "school", "اسکول"), ("die Universität", "university", "یونیورسٹی"),
        ("das Buch", "book", "کتاب"), ("der Stift", "pen", "قلم"), ("das Papier", "paper", "کاغذ"),
        ("die Tasche", "bag", "بیگ / تھیلا"), ("das Geld", "money", "پیسہ"),
        ("der Euro", "euro", "یورو"), ("der Preis", "price", "قیمت"),
        ("der Rechnungsbetrag", "bill amount", "بل کی رقم"), ("der Markt", "market", "بازار"),
        ("der Supermarkt", "supermarket", "سپر مارکیٹ"), ("die Bäckerei", "bakery", "بیکری"),
        ("das Geschäft", "shop / store", "دکان"), ("kaufen", "to buy", "خریدنا"),
        ("verkaufen", "to sell", "بیچنا"), ("bezahlen", "to pay", "ادائیگی کرنا"),
        ("kosten", "to cost", "قیمت ہونا"), ("suche", "search / look for", "تلاش کرنا"),
        ("der Tag", "day", "دن"), ("die Nacht", "night", "رات"), ("der Morgen", "morning", "صبح"),
        ("der Abend", "evening", "شام"), ("die Woche", "week", "ہفتہ"), ("der Monat", "month", "مہینہ"),
        ("das Jahr", "year", "سال"), ("heute", "today", "آج"), ("morgen", "tomorrow", "کل (آنے والا)"),
        ("gestern", "yesterday", "کل (گزرا ہوا)"), ("jetzt", "now", "ابھی"),
        ("später", "later", "بعد میں"), ("immer", "always", "ہمیشہ"), ("nie", "never", "کبھی نہیں"),
        ("oft", "often", "اکثر"), ("manchmal", "sometimes", "کبھی کبھی"),
        ("groß", "big / tall", "بڑا"), ("klein", "small / short", "چھوٹا"),
        ("alt", "old", "پرانا / بوڑھا"), ("neu", "new", "نیا"),
        ("gut", "good", "اچھا"), ("schlecht", "bad", "برا"),
        ("schön", "beautiful", "خوبصورت"), ("hässlich", "ugly", "بدصورت"),
        ("schnell", "fast", "تیز"), ("langsam", "slow", "سست"),
        ("laut", "loud", "اونچی آواز"), ("leise", "quiet", "خاموش"),
        ("heiß", "hot", "گرم"), ("kalt", "cold", "ٹھنڈا"),
        ("einfach", "simple / easy", "آسان"), ("schwer", "difficult / heavy", "مشکل / بھاری"),
        ("richtig", "correct", "صحیح"), ("falsch", "wrong", "غلط"),
        ("voll", "full", "بھرا ہوا"), ("leer", "empty", "خالی"),
        ("früh", "early", "جلدی"), ("spät", "late", "دیر"),
        ("fahren", "to drive / ride", "گاڑی چلانا / سفر کرنا"), ("gehen", "to go / walk", "جانا / چلنا"),
        ("kommen", "to come", "آنا"), ("wohnen", "to reside / live", "رہنا"),
        ("leben", "to live", "زندہ رہنا"), ("arbeiten", "to work", "کام کرنا"),
        ("lernen", "to learn / study", "سیکھنا"), ("schreiben", "to write", "لکھنا"),
        ("lesen", "to read", "پڑھنا"), ("sprechen", "to speak", "بولنا"),
        ("verstehen", "to understand", "سمجھنا"), ("hören", "to hear / listen", "سننا"),
        ("sehen", "to see", "دیکھنا"), ("essen", "to eat", "کھانا"),
        ("trinken", "to drink", "پینا"), ("schlafen", "to sleep", "سونا"),
        ("machen", "to do / make", "کرنا / بنانا"), ("haben", "to have", "پاس ہونا"),
        ("sein", "to be", "ہونا"), ("werden", "to become", "بننا"),
        ("können", "can / to be able to", "سکنا"), ("müssen", "must / to have to", "لازمی ہونا"),
        ("wollen", "want to", "چاہنا"), ("möchten", "would like to", "پسند کرنا"),
        ("sollen", "should / supposed to", "چاہیے"), ("dürfen", "may / allowed to", "اجازت ہونا")
    ],
    "A2": [
        ("die Ausbildung", "vocational training", "پیشہ ورانہ تربیت / آوسبلڈنگ"),
        ("der Ausbildungsplatz", "apprenticeship position", "تربیت کی جگہ"),
        ("das Bewerbungsschreiben", "job application", "نوکری کی درخواست"),
        ("der Lebenslauf", "resume / CV", "سی وی / تعلیمی ریکارڈ"),
        ("das Vorstellungsgespräch", "job interview", "انٹرویو"),
        ("der Vertrag", "contract", "معاہدہ / ایگریمنٹ"),
        ("das Gehalt", "salary", "تنخواہ"),
        ("der Chef", "boss (male)", "بوس / سربراہ"),
        ("die Chefin", "boss (female)", "خاتون سربراہ"),
        ("der Kollege", "colleague (male)", "ساتھی"),
        ("die Kollegin", "colleague (female)", "خاتون ساتھی"),
        ("die Krankenversicherung", "health insurance", "صحت کی انشورنس"),
        ("die Rentenversicherung", "pension insurance", "پینشن انشورنس"),
        ("die Steuer", "tax", "ٹیکس"),
        ("das Formular", "form", "فارم"),
        ("der Antrag", "application / motion", "درخواست"),
        ("die Behörde", "government authority", "سرکاری دفتر / اتھارٹی"),
        ("der Pass", "passport", "پاسپورٹ"),
        ("der Ausweis", "ID card", "شناختی کارڈ"),
        ("die Anmeldung", "registration", "رجسٹریشن"),
        ("die Abmeldung", "de-registration", "رجسٹریشن کی منسوخی"),
        ("die Bestätigung", "confirmation", "تصدیق"),
        ("der Mietvertrag", "rental lease contract", "کرائے کا معاہدہ"),
        ("die Miete", "rent", "کراایہ"),
        ("die Kaution", "security deposit", "ضمانتی رقم"),
        ("die Nebenkosten", "utility costs", "اضافی اخراجات"),
        ("die Heizung", "heating system", "ہیٹنگ / گرمائش"),
        ("der Strom", "electricity", "بجلی"),
        ("das Internet", "internet", "انٹرنیٹ"),
        ("der Nachbar", "neighbor (male)", "پڑوسی"),
        ("die Nachbarin", "neighbor (female)", "خاتون پڑوسی"),
        ("die Kündigung", "notice of termination", "استعفیٰ / منسوخی"),
        ("der Arzttermin", "doctor appointment", "ڈاکٹر کی ملاقات"),
        ("die Praxis", "doctor's clinic", "کلینک"),
        ("das Krankenhaus", "hospital", "ہسپتال"),
        ("die Apotheke", "pharmacy", "میڈیکل اسٹور"),
        ("das Medikament", "medicine", "دوا"),
        ("die Rezept", "prescription / recipe", "نسخہ / ترکیب"),
        ("die Schmerzen", "pain / aches", "درد"),
        ("Fieber", "fever", "بخار"),
        ("Husten", "cough", "کھانسی"),
        ("Schnupfen", "runny nose / cold", "زکام"),
        ("die Gesundheit", "health", "صحت"),
        ("gesund", "healthy", "صحت مند"),
        ("krank", "sick / ill", "بیمار"),
        ("die Verspätung", "delay", "تاخیر / دیری"),
        ("pünktlich", "punctual", "وقت کا پابند"),
        ("der Anschluss", "connecting train/bus", "کنیکٹنگ ٹرین"),
        ("das Gleis", "platform / track", "پلیٹ فارم"),
        ("der Umstieg", "transfer / change trains", "ٹرین کی تبدیلی"),
        ("die Abfahrt", "departure", "روانگی"),
        ("die Ankunft", "arrival", "آمد"),
        ("die Reise", "trip / journey", "سفر"),
        ("das Gepäck", "luggage / baggage", "سامان"),
        ("der Koffer", "suitcase", "سوٹ کیس"),
        ("das Hotel", "hotel", "ہوٹل"),
        ("die Übernachtung", "overnight stay", "رات کا قیام"),
        ("buchen", "to book / reserve", "بک کرنا"),
        ("reservieren", "to reserve", "ریزرو کرنا"),
        ("stornieren", "to cancel", "منسوخ کرنا"),
        ("überweisen", "to transfer money", "رقم منتقل کرنا"),
        ("sparen", "to save money", "بچت کرنا"),
        ("ausgeben", "to spend money", "خرچ کرنا"),
        ("verleihen", "to lend", "ادھار دینا"),
        ("leihen", "to borrow", "ادھار لینا"),
        ("empfehlen", "to recommend", "سفارش کرنا"),
        ("erklären", "to explain", "وضاحت کرنا"),
        ("beschreiben", "to describe", "بیان کرنا"),
        ("vergleichen", "to compare", "موازنہ کرنا"),
        ("unterscheiden", "to distinguish", "فرق کرنا"),
        ("entscheiden", "to decide", "فیصلہ کرنا"),
        ("versuchen", "to try / attempt", "کوشش کرنا"),
        ("probieren", "to test / taste", "آزمانا / چکھنا"),
        ("passen", "to fit / suit", "مناسب ہونا"),
        ("gehören", "to belong to", "ملکیت ہونا"),
        ("gefallen", "to please / like", "پسند آنا"),
        ("danken", "to thank", "شکریہ ادا کرنا"),
        ("helfen", "to help", "مدد کرنا"),
        ("gratulieren", "to congratulate", "مبارکباد دینا"),
        ("antworten", "to answer", "جواب دینا"),
        ("fragen", "to ask", "پوچھنا"),
        ("bitten", "to request", "درخواست کرنا"),
        ("danken", "to thank", "شکریہ کہنا"),
        ("hoffen", "to hope", "امید کرنا"),
        ("glauben", "to believe / think", "یقین رکھنا / سوچنا"),
        ("meinen", "to mean / think", "مراد ہونا / خیال ہونا"),
        ("wissen", "to know a fact", "جاننا"),
        ("kennen", "to know a person/place", "شناسائی ہونا"),
        ("denken", "to think", "سوچنا"),
        ("erinnern", "to remember", "یاد کرنا"),
        ("vergessen", "to forget", "بھولنا"),
        ("verlieren", "to lose", "کھونا / ہارنا"),
        ("gewinnen", "to win", "جیتنا"),
        ("suchen", "to search", "تلاش کرنا"),
        ("finden", "to find", "پانا / ملنا"),
        ("bringen", "to bring", "لانا"),
        ("mitbringen", "to bring along", "ساتھ لانا"),
        ("abholen", "to pick up", "لینے جانا"),
        ("anrufen", "to call", "فون کرنا"),
        ("mitkommen", "to come along", "ساتھ آنا"),
        ("einladen", "to invite", "دعوت دینا"),
        ("mitmachen", "to participate", "حصہ لینا"),
        ("anfangen", "to begin", "شروع کرنا"),
        ("aufhören", "to stop / cease", "روکنا / ختم کرنا"),
        ("aufstehen", "to get up", "اٹھنا"),
        ("einschlafen", "to fall asleep", "سو جانا"),
        ("anziehen", "to put on clothes", "کپڑے پہننا"),
        ("ausziehen", "to take off clothes / move out", "کپڑے اتارنا / مکان چھوڑنا"),
        ("umziehen", "to move house / change clothes", "مکان بدلنا"),
        ("waschen", "to wash", "دھونا"),
        ("duschen", "to shower", "نہانا"),
        ("aufräumen", "to clean up", "صفائی کرنا"),
        ("saubermachen", "to clean", "صاف کرنا"),
        ("kochen", "to cook", "پکانا"),
        ("backen", "to bake", "بیک کرنا"),
        ("frühstücken", "to eat breakfast", "ناشتہ کرنا"),
        ("schmecken", "to taste good", "ذائقہ دار ہونا"),
        ("bestellen", "to order", "آرڈر دینا"),
        ("zahlen", "to pay", "ادائیگی کرنا"),
        ("probieren", "to try out", "آزمانا"),
        ("besuchen", "to visit", "ملاقات کرنا"),
        ("treffen", "to meet", "ملنا"),
        ("kennenlernen", "to get to know", "تعارف حاصل کرنا"),
        ("heiraten", "to marry", "شادی کرنا"),
        ("streiten", "to argue", "جھگڑا کرنا"),
        ("lachen", "to laugh", "ہنسنا"),
        ("weinen", "to cry", "رونا"),
        ("freuen", "to look forward / be glad", "خوش ہونا"),
        ("ärgern", "to annoy / get angry", "ناراض ہونا"),
        ("hoffen", "to hope", "امید رکھنا"),
        ("wünschen", "to wish", "خواہش کرنا"),
        ("träumen", "to dream", "خواب دیکھنا"),
        ("planen", "to plan", "منصوبہ بنانا"),
        ("reisen", "to travel", "سفر کرنا"),
        ("wandern", "to hike", "پہاڑی پیدل سفر"),
        ("schwimmen", "to swim", "تیرنا"),
        ("tanzen", "to dance", "رقص کرنا"),
        ("singe", "sing", "گانا"),
        ("spielen", "to play", "کھیلنا"),
        ("gewinnen", "to win", "جیتنا"),
        ("verlieren", "to lose", "ہارنا"),
        ("funktionieren", "to function / work", "کام کرنا"),
        ("reparieren", "to repair", "مرمت کرنا"),
        ("brauchen", "to need", "ضرورت ہونا"),
        ("benutzen", "to use", "استعمال کرنا"),
        ("öffnen", "to open", "کھولنا"),
        ("schließen", "to close", "بند کرنا"),
        ("anmachen", "to turn on", "آن کرنا"),
        ("ausmachen", "to turn off", "آف کرنا")
    ],
    "B1": [
        ("die Arbeitslosigkeit", "unemployment", "بے روزگاری"),
        ("die Herausforderung", "challenge", "چیلنج / مشکل"),
        ("die Nachhaltigkeit", "sustainability", "پائیداری"),
        ("die Verantwortung", "responsibility", "ذمہ داری"),
        ("die Voraussetzung", "requirement / prerequisite", "شرط / بنیادی ضرورت"),
        ("die Entwicklung", "development", "ترقی / پیش رفت"),
        ("die Gesellschaft", "society", "معاشرہ"),
        ("die Wirtschaft", "economy", "معیشت"),
        ("die Beziehung", "relationship", "تعلق / رشتہ"),
        ("die Begeisterung", "enthusiasm", "جوش و جذبہ"),
        ("die Behauptung", "assertion / claim", "دعویٰ"),
        ("die Auswirkung", "impact / effect", "اثر / نتیجہ"),
        ("die Verhandlung", "negotiation", "مذاکرات / بات چیت"),
        ("die Entscheidung", "decision", "فیصلہ"),
        ("die Zustimmung", "agreement / consent", "رضامندی"),
        ("die Ablehnung", "rejection / refusal", "انکار / مستردگی"),
        ("die Gelegenheit", "opportunity / occasion", "موقع"),
        ("die Erfahrung", "experience", "تجربہ"),
        ("die Kenntnis", "knowledge / skill", "معلومات / مہارت"),
        ("die Fähigkeit", "ability / capability", "صلاحیت / قابلیت"),
        ("die Lösung", "solution", "حل"),
        ("das Ergebnis", "result / outcome", "نتیجہ"),
        ("der Unterschied", "difference", "فرق"),
        ("der Vergleich", "comparison", "موازنہ"),
        ("der Vorteil", "advantage", "فائدہ"),
        ("der Nachteil", "disadvantage", "نقصان / کمی"),
        ("die Ursache", "cause / reason", "وجہ / سبب"),
        ("die Wirkung", "effect / response", "اثر"),
        ("der Einfluss", "influence", "اثر و رسوخ"),
        ("die Zunahme", "increase / growth", "اضافہ"),
        ("die Abnahme", "decrease / decline", "کمی"),
        ("die Maßnahme", "measure / action", "اقدام"),
        ("der Umweltschutz", "environmental protection", "ماحولیاتی تحفظ"),
        ("der Klimawandel", "climate change", "موسمیاتی تبدیلی"),
        ("die Erwärmung", "warming", "شدتِ حرارت"),
        ("die Zukunft", "future", "مستقبل"),
        ("die Vergangenheit", "past", "مضی"),
        ("die Gegenwart", "present / current time", "موجودہ دور"),
        ("die Öffentlichkeit", "public", "عوام / پبلک"),
        ("die Meinung", "opinion", "رائے"),
        ("der Standpunkt", "point of view", "موقف / نقطہ نظر"),
        ("die Überzeugung", "conviction / belief", "پختہ یقین"),
        ("das Argument", "argument", "دلیل"),
        ("der Beweis", "proof / evidence", "ثبوت"),
        ("die Bedingung", "condition / terms", "شرط"),
        ("die Ausnahme", "exception", "استثنیٰ"),
        ("der Zusammenhang", "context / connection", "تعلق / سیاق و سباق"),
        ("die Eigenschaft", "property / quality", "خصوصیت"),
        ("die Verpflichtung", "obligation / commitment", "فرائض / پابندی"),
        ("die Begründung", "justification / reason", "جواز / وجہ"),
        ("berücksichtigen", "to take into account", "مدنظر رکھنا"),
        ("beeinflussen", "to influence", "متاثر کرنا"),
        ("verhindern", "to prevent / stop", "روکنا / بچانا"),
        ("verbessern", "to improve", "بہتر بنانا"),
        ("verschlechtern", "to worsen", "خراب ہونا"),
        ("unterstützen", "to support / assist", "حمایت کرنا"),
        ("fördern", "to promote / encourage", "ترغیب دینا"),
        ("fordern", "to demand", "مطالبہ کرنا"),
        ("verlangen", "to demand / require", "تقاضا کرنا"),
        ("empfehlen", "to recommend", "سفارش کرنا"),
        ("überzeugen", "to convince", "قائل کرنا"),
        ("überreden", "to persuade", "راضی کرنا"),
        ("widerlegen", "to refute", "تردید کرنا"),
        ("bestätigen", "to confirm", "تصدیق کرنا"),
        ("behaupten", "to claim", "دعویٰ کرنا"),
        ("vermuten", "to suspect / presume", "گمان کرنا"),
        ("annehmen", "to assume / accept", "فرض کرنا / قبول کرنا"),
        ("ablehnen", "to decline / reject", "مسترد کرنا"),
        ("zustimmen", "to agree", "متفق ہونا"),
        ("widersprechen", "to contradict", "مخالفت کرنا"),
        ("diskutieren", "to discuss", "بحث کرنا"),
        ("verhandeln", "to negotiate", "مذاکرات کرنا"),
        ("beschließen", "to decide / resolve", "فیصلہ کرنا"),
        ("erreichen", "to achieve / reach", "حاصل کرنا / پہنچنا"),
        ("scheitern", "to fail / collapse", "ناکام ہونا"),
        ("beseitigen", "to eliminate", "ختم کرنا"),
        ("überwinden", "to overcome", "قابو پانا"),
        ("lösen", "to solve", "حل کرنا"),
        ("verändern", "to alter / change", "تبدیل کرنا"),
        ("entwickeln", "to develop", "ترقی دینا"),
        ("entstehen", "to originate / arise", "وجود میں آنا"),
        ("vergehen", "to pass time", "وقت گزرنا"),
        ("geschehen", "to happen", "واقع ہونا"),
        ("passieren", "to occur", "پیش آنا"),
        ("verursachen", "to cause", "سبب بننا"),
        ("bewirken", "to bring about", "اثر انداز ہونا"),
        ("führen zu", "to lead to", "سبب بننا"),
        ("abhängen von", "to depend on", "انحصار ہونا"),
        ("beitragen zu", "to contribute to", "حصہ ڈالنا"),
        ("teilnehmen an", "to participate in", "شرکت کرنا"),
        ("sich beteiligen an", "to take part in", "شامل ہونا"),
        ("verzichten auf", "to do without", "دستبردار ہونا"),
        ("achten auf", "to pay attention to", "دھیان دینا"),
        ("aufpassen auf", "to look after", "دیکھ بھال کرنا"),
        ("kümern um", "to care for", "فکر کرنا"),
        ("sorgen für", "to provide for", "انتظام کرنا"),
        ("rechnen mit", "to reckon with / expect", "توقع رکھنا"),
        ("reagieren auf", "to react to", "ردعمل دینا"),
        ("gehören zu", "to belong to", "شامل ہونا")
    ]
}

async def bulk_seed_vocabulary_pipeline():
    print("=========================================================================")
    print("[Ingestion Engine] DeutschMind Pre-Seeded Vocabulary Ingestion Pipeline")
    print("=========================================================================\n")

    init_goethe_vocab_schema()
    conn = get_db_connection()
    cursor = conn.cursor()

    total_new_records = 0
    BATCH_SIZE = 20
    PAUSE_SLEEP_SECONDS = 0.2

    for level, words_data in VOCAB_DATASETS.items():
        print(f"--- Ingesting {len(words_data)} Goethe-Institut Vocabulary Words for Level [{level}] ---")
        
        inserted_for_level = 0
        for i in range(0, len(words_data), BATCH_SIZE):
            batch = words_data[i:i + BATCH_SIZE]
            
            for item in batch:
                german_word, english_trans, urdu_trans = item[0], item[1], item[2]
                example_sentence = f"Das Wort '{german_word}' gehört zum Goethe {level} Wortschatz."
                
                try:
                    cursor.execute("""
                    INSERT OR IGNORE INTO goethe_vocabulary 
                    (german_word, cefr_level, english_translation, urdu_translation, example_sentence)
                    VALUES (?, ?, ?, ?, ?);
                    """, (german_word, level, english_trans, urdu_trans, example_sentence))
                    
                    if cursor.rowcount > 0:
                        inserted_for_level += 1
                        total_new_records += 1
                except sqlite3.Error as err:
                    print(f"[{level}] Skipped item '{german_word}': {err}")

            conn.commit()
            await asyncio.sleep(PAUSE_SLEEP_SECONDS)

        print(f"[{level}] Complete: {inserted_for_level} new unique records inserted into SQLite.\n")

    # Fetch total database row count
    cursor.execute("SELECT COUNT(*) AS total_count FROM goethe_vocabulary;")
    total_db_count = cursor.fetchone()["total_count"]
    conn.close()

    # Step 6: Overwrite static JSON export file (vocab.json)
    print("Exporting newly expanded SQLite database pool to static JSON...")
    export_sqlite_to_static_json()

    print("\n=========================================================================")
    print(f"[Success] BULK VOCABULARY INGESTION COMPLETE!")
    print(f"Total New Records Inserted in this session: {total_new_records}")
    print(f"Total Database Row Count (goethe_vocabulary): {total_db_count} records")
    print("=========================================================================")

if __name__ == "__main__":
    asyncio.run(bulk_seed_vocabulary_pipeline())
