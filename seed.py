
import csv, os, sqlite3

BASE = os.path.dirname(__file__)
DB = os.path.join(BASE, 'inhouse.sqlite3')

def upsert(cur, table, cols, row, conflict='IGNORE'):
    keys = ','.join(cols)
    qs = ','.join(['?']*len(cols))
    sql = f"INSERT OR {conflict} INTO {table}({keys}) VALUES({qs})"
    cur.execute(sql, row)

def load_csv(cur, fname, table, cols):
    path = os.path.join(BASE, fname)
    if not os.path.exists(path): 
        print('skip', fname)
        return
    with open(path, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for d in r:
            row = [d[c] for c in cols]
            upsert(cur, table, cols, row)

def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    load_csv(cur, 'employees.csv', 'employees', ['name','email','team'])
    load_csv(cur, 'desks.csv', 'desks', ['label','floor'])
    load_csv(cur, 'rooms.csv', 'rooms', ['name','capacity','floor'])
    load_csv(cur, 'assets.csv', 'assets', ['asset_code','name','type','location'])
    # seed some vacation/company events if CSVs exist
    # vacations.csv -> events(kind='vac', title=name, start,end)
    vpath = os.path.join(BASE, 'vacations.csv')
    if os.path.exists(vpath):
        with open(vpath, newline='', encoding='utf-8') as f:
            r = csv.DictReader(f)
            for d in r:
                cur.execute("INSERT INTO events(kind, owner_email, title, start, end) VALUES('vac', ?, ?, ?, ?)",
                            (d.get('email'), d.get('name'), d.get('start'), d.get('end')))
    cpath = os.path.join(BASE, 'company_events.csv')
    if os.path.exists(cpath):
        with open(cpath, newline='', encoding='utf-8') as f:
            r = csv.DictReader(f)
            for d in r:
                cur.execute("INSERT INTO events(kind, owner_email, title, start, end, location, body, link) VALUES('company', ?, ?, ?, ?, ?, ?, ?)",
                            (d.get('created_by'), d.get('title'), d.get('start'), d.get('end'), d.get('location'), d.get('body'), d.get('link')))
    con.commit()
    con.close()
    print('Seed complete.')

if __name__ == '__main__':
    main()
