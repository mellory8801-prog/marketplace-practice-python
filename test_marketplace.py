import unittest
from marketplace import connect,seed,checkout,cancel,total

class MarketplaceTests(unittest.TestCase):
    def setUp(self):
        self.db=connect(':memory:'); seed(self.db)
    def tearDown(self): self.db.close()
    def stock(self,pid=1):
        return self.db.execute('SELECT stock FROM products WHERE id=?',(pid,)).fetchone()[0]
    def test_01_total(self):
        self.assertEqual(total(self.db,checkout(self.db,1,{1:2,2:1},'a')),677000)
    def test_02_stock(self):
        checkout(self.db,1,{1:2},'a'); self.assertEqual(self.stock(),6)
    def test_03_no_stock(self):
        with self.assertRaises(ValueError): checkout(self.db,1,{3:1},'a')
    def test_04_rollback(self):
        with self.assertRaises(ValueError): checkout(self.db,1,{1:2,3:1},'a')
        self.assertEqual(self.stock(),8)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM orders').fetchone()[0],0)
    def test_05_repeat(self):
        a=checkout(self.db,1,{1:2},'a'); b=checkout(self.db,1,{1:2},'a')
        self.assertEqual(a,b); self.assertEqual(self.stock(),6)
    def test_06_negative(self):
        with self.assertRaises(ValueError): checkout(self.db,1,{1:-1},'a')
    def test_07_role(self):
        with self.assertRaises(PermissionError): checkout(self.db,2,{1:1},'a')
    def test_08_cancel(self):
        a=checkout(self.db,1,{1:2},'a'); cancel(self.db,1,a)
        self.assertEqual(self.stock(),8)
    def test_09_repeat_cancel(self):
        a=checkout(self.db,1,{1:2},'a'); cancel(self.db,1,a); cancel(self.db,1,a)
        self.assertEqual(self.stock(),8)
    def test_10_foreign_cancel(self):
        a=checkout(self.db,1,{1:2},'a')
        with self.assertRaises(PermissionError): cancel(self.db,4,a)
    def test_11_price_snapshot(self):
        a=checkout(self.db,1,{1:1},'a')
        self.db.execute('UPDATE products SET price=100 WHERE id=1')
        self.assertEqual(total(self.db,a),249000)
    def test_12_empty(self):
        with self.assertRaises(ValueError): checkout(self.db,1,{},'a')

if __name__=='__main__': unittest.main(verbosity=2)
