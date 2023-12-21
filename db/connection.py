import pyodbc    



class DBConnection:
    def __init__(self, address, database, username, password):
        conn_string = \
            f'DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={address};DATABASE={database};UID={username};PWD={password};Encrypt=no'
        self.conn = pyodbc.connect(conn_string)


    def get_new_numbers(self, nums):
        if not nums:
            return []
        
        nums_str = ', '.join(f"('{num}')" for num in nums)
        query1 = \
f"""
IF (OBJECT_ID('tempdb..#RTSTempCollected') IS NOT NULL) 
	DROP TABLE #RTSTempCollected

CREATE TABLE #RTSTempCollected (notifnr varchar(50))

INSERT INTO #RTSTempCollected
VALUES {nums_str}
"""
        query2 = \
"""
SELECT distinct t.notifnr 
FROM #RTSTempCollected t
LEFT JOIN [cursorimport].import.notifications44 n
    ON t.notifnr = n.notificationnumber
WHERE n.id_Notification is NULL
"""

        cursor = self.conn.cursor()
        cursor.execute(query1)
        cursor.execute(query2)
        ret = [num[0] for num in cursor.fetchall()]
        cursor.close()
        
        return ret
    
    def close(self):
        self.conn.close()
