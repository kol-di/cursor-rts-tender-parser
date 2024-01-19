import pyodbc    



class DBConnection:
    def __init__(self, address, database, username, password):
        conn_string = \
            f'DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={address};DATABASE={database};UID={username};PWD={password};Encrypt=no'
        self.conn = pyodbc.connect(conn_string)


    def get_new_numbers(self, collected, fz):
        if not collected:
            return []
        if fz == '44':
            nums = collected
        elif fz == '223':
            nums = [col.notif_num for col in collected]
        
        query1 = \
"""
IF (OBJECT_ID('tempdb..#RTSTempCollected') IS NOT NULL) 
	DROP TABLE #RTSTempCollected

CREATE TABLE #RTSTempCollected (notifnr varchar(50))
"""
        query2 = lambda nums_str: \
f"""
INSERT INTO #RTSTempCollected
VALUES {nums_str}
"""
        query3 = \
f"""
SELECT distinct t.notifnr 
FROM #RTSTempCollected t
LEFT JOIN [cursorimport].import.notifications{'223' if fz == '223' else '44'} n
    ON t.notifnr = n.notificationnumber
WHERE n.id_Notification is NULL
"""

        cursor = self.conn.cursor()
        cursor.execute(query1)
        
        slice_sz = 999
        for nums_slice in [nums[i:i + slice_sz] for i in range(0, len(nums), slice_sz)]:
            nums_str = ', '.join(f"('{num}')" for num in nums_slice)
            cursor.execute(query2(nums_str))

        cursor.execute(query3)
        new_nums = [num[0] for num in cursor.fetchall()]
        cursor.close()
        
        if fz == '44':
            new_collected = new_nums
        elif fz == '223':
            new_collected = [col for col in collected if col.notif_num in new_nums]

        return new_collected
    
    def close(self):
        self.conn.close()
