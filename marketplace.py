"""Учебное ядро информационной системы маркетплейса. Python 3.11+."""
import sqlite3
from pathlib import Path

SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users(
 id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE,
 role TEXT NOT NULL CHECK(role IN ('buyer','seller','admin')));
CREATE TABLE IF NOT EXISTS categories(
 id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS products(
 id INTEGER PRIMARY KEY, seller_id INTEGER NOT NULL REFERENCES users(id),
 category_id INTEGER NOT NULL REFERENCES categories(id),
 name TEXT NOT NULL, price INTEGER NOT NULL CHECK(price>0),
 stock INTEGER NOT NULL CHECK(stock>=0),
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)));
CREATE TABLE IF NOT EXISTS orders(
 id INTEGER PRIMARY KEY, buyer_id INTEGER NOT NULL REFERENCES users(id),
 request_key TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new'
 CHECK(status IN ('new','confirmed','shipped','completed','cancelled')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(buyer_id,request_key));
CREATE TABLE IF NOT EXISTS order_items(
 id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id),
 product_id INTEGER NOT NULL REFERENCES products(id),
 quantity INTEGER NOT NULL CHECK(quantity>0),
 unit_price INTEGER NOT NULL CHECK(unit_price>0),
 UNIQUE(order_id,product_id));
CREATE TABLE IF NOT EXISTS audit_log(
 id INTEGER PRIMARY KEY, actor_id INTEGER NOT NULL REFERENCES users(id),
 order_id INTEGER NOT NULL REFERENCES orders(id), action TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
'''

def connect(path='marketplace.db'):
    db=sqlite3.connect(path, timeout=10, isolation_level=None)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript(SCHEMA)
    return db

def seed(db):
    db.executemany('INSERT OR IGNORE INTO users VALUES(?,?,?)',[
        (1,'buyer@example.test','buyer'),(2,'seller@example.test','seller'),
        (3,'admin@example.test','admin'),(4,'other@example.test','buyer')])
    db.executemany('INSERT OR IGNORE INTO categories VALUES(?,?)',[(1,'Электроника'),(2,'Дом')])
    db.executemany('INSERT OR IGNORE INTO products VALUES(?,?,?,?,?,?,?)',[
        (1,2,1,'Беспроводные наушники',249000,8,1),
        (2,2,2,'Настольная лампа',179000,5,1),
        (3,2,1,'Клавиатура',329000,0,1)])

def checkout(db, buyer_id, items, request_key):
    """items = {product_id: quantity}; стоимость всегда берётся из БД."""
    if not isinstance(request_key,str) or not request_key.strip():
        raise ValueError('Не задан ключ запроса')
    if not items or any(type(q) is not int or q <= 0 for q in items.values()):
        raise ValueError('Некорректное количество')
    db.execute('BEGIN IMMEDIATE')
    try:
        buyer=db.execute('SELECT role FROM users WHERE id=?',(buyer_id,)).fetchone()
        if not buyer or buyer['role']!='buyer':
            raise PermissionError('Оформление доступно покупателю')
        old=db.execute('SELECT id FROM orders WHERE buyer_id=? AND request_key=?',
                       (buyer_id,request_key)).fetchone()
        if old:
            db.commit()
            return old['id']
        oid=db.execute('INSERT INTO orders(buyer_id,request_key) VALUES(?,?)',
                       (buyer_id,request_key)).lastrowid
        for pid,qty in sorted(items.items()):
            p=db.execute('SELECT * FROM products WHERE id=? AND active=1',(pid,)).fetchone()
            if not p:
                raise ValueError('Товар недоступен')
            changed=db.execute('UPDATE products SET stock=stock-? WHERE id=? AND stock>=?',
                               (qty,pid,qty)).rowcount
            if changed!=1:
                raise ValueError('Недостаточно товара')
            db.execute('INSERT INTO order_items(order_id,product_id,quantity,unit_price) VALUES(?,?,?,?)',
                       (oid,pid,qty,p['price']))
        db.execute('INSERT INTO audit_log(actor_id,order_id,action) VALUES(?,?,?)',
                   (buyer_id,oid,'created'))
        db.commit()
        return oid
    except Exception:
        db.rollback()
        raise

def cancel(db, buyer_id, order_id):
    db.execute('BEGIN IMMEDIATE')
    try:
        o=db.execute('SELECT * FROM orders WHERE id=?',(order_id,)).fetchone()
        if not o or o['buyer_id']!=buyer_id:
            raise PermissionError('Заказ недоступен')
        if o['status']=='cancelled':
            db.commit()
            return
        if o['status']!='new':
            raise ValueError('Отмена недоступна')
        for item in db.execute('SELECT * FROM order_items WHERE order_id=?',(order_id,)).fetchall():
            db.execute('UPDATE products SET stock=stock+? WHERE id=?',
                       (item['quantity'],item['product_id']))
        db.execute("UPDATE orders SET status='cancelled' WHERE id=?",(order_id,))
        db.execute('INSERT INTO audit_log(actor_id,order_id,action) VALUES(?,?,?)',
                   (buyer_id,order_id,'cancelled'))
        db.commit()
    except Exception:
        db.rollback()
        raise

def total(db, order_id):
    return db.execute('SELECT COALESCE(SUM(quantity*unit_price),0) FROM order_items WHERE order_id=?',
                      (order_id,)).fetchone()[0]

if __name__=='__main__':
    db=connect(); seed(db)
    oid=checkout(db,1,{1:2,2:1},'demo-order-001')
    print(f'Заказ {oid}. Сумма: {total(db,oid)/100:.2f} руб.')
    db.close()
