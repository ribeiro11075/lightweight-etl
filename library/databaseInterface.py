#import mysql.connector
#import cx_Oracle
import psycopg2


class DATABASE():

	def __init__(self, connectionSettings):
		self.connectionSettings = connectionSettings

		# connect to database
		self.connect()


	def connect(self):

		# define variables
		self.type = self.connectionSettings['type']
		user = self.connectionSettings['user']
		password = self.connectionSettings['password']
		database = self.connectionSettings['database']
		host = self.connectionSettings['host']
		port = self.connectionSettings['port'] if self.connectionSettings['port'] else None
		threaded = self.connectionSettings['threaded'] if self.connectionSettings['threaded'] else None
		serviceName = self.connectionSettings['serviceName'] if self.connectionSettings['serviceName'] else None
		sid = self.connectionSettings['sid'] if self.connectionSettings['sid'] else None


		# check database type and connection protocols
		# connect to database
		if self.type == 'mysql':
			self.connection = mysql.connector.connect(user=user, password=password, host=host, database=database, port=port)
			self.cursor = self.connection.cursor(buffered=True)
		elif self.type == 'oracle' and serviceName:
			self.connection = cx_Oracle.connect(user=user, password=password, threaded=threaded, dsn=cx_Oracle.makedsn(host=host, port=port, serviceName=serviceName))
			self.cursor = self.connection.cursor()
		elif self.type == 'oracle' and sid:
			self.connection = cx_Oracle.connect(user=user, password=password, threaded=threaded, dsn=cx_Oracle.makedsn(host=host, port=port, sid=sid))
			self.cursor = self.connection.cursor()
		elif self.type == 'postgresql':
			self.connection = psycopg2.connect(user=user, password=password, host=host, database=database, port=port)
			self.cursor = self.connection.cursor()


	def close(self):

		# close cursor & connection
		self.cursor.close()
		self.connection.close()


	def query(self, query):

		# execute query & fetch results from execution
		self.cursor.execute(query)
		data = self.cursor.fetchall()

		return data


	def alter(self, query):

		# execute query & commit
		self.cursor.execute(query)
		self.connection.commit()


	def truncate(self, table):

		# dynamically create SQL
		# execute query & commit
		query = "TRUNCATE TABLE {}".format(table)
		self.cursor.execute(query)
		self.connection.commit()


	# Needs to be fixed to accomodate PostgreSQL
	def getAllColumnTypes(self, table):

		query = "SELECT * FROM {}".format(table)

		# execute query & fetch results from execution
		self.cursor.execute(query)
		columnTypes = [row[1] for row in self.cursor.description]


		return columnTypes


	def getAllColumnNames(self, table):

		query = "SELECT * FROM {}".format(table)

		# execute query & fetch results from execution
		self.cursor.execute(query)
		columns = [row[0] for row in self.cursor.description]

		return columns


	# Needs to be fixed to accomodate PostgreSQL
	def getPrimaryColumnNames(self, table):

		# execute query & fetch results from execution
		if self.type == 'mysql':
			query = "SELECT k.COLUMN_NAME FROM information_schema.table_constraints t LEFT JOIN information_schema.key_column_usage k USING(constraint_name, table_schema, table_name) WHERE t.constraint_type='PRIMARY KEY' AND t.table_name='owalog'"
		elif self.type == 'postgresql':
			query = "SELECT c.column_name FROM information_schema.key_column_usage AS c LEFT JOIN information_schema.table_constraints AS t ON t.constraint_name=c.constraint_name WHERE t.table_name='{}' AND t.constraint_type in ('PRIMARY KEY', 'UNIQUE')".format(table)

		self.cursor.execute(query)
		columns = [row[0] for row in self.cursor.fetchall()]

		return columns


	def getNonPrimaryColumnNames(self, table):

		allColumns = self.getAllColumnNames(table=table)
		primaryColumns = self.getPrimaryColumnNames(table=table)
		nonPrimaryColumns = [i for i in allColumns if i not in primaryColumns]

		return nonPrimaryColumns


	# Needs to be fixed to accomodate PostgreSQL
	def _getColumnBuckets(self, table):

		allColumns = self.getAllColumnNames(table=table)
		primaryColumns = self.getPrimaryColumnNames(table=table)
		nonPrimaryColumns = [i for i in allColumns if i not in primaryColumns]

		return allColumns, primaryColumns, nonPrimaryColumns


	def _chunkInsert(self, table, data, chunkSize, query):

		# define index to track which rows to insert with chunking
		# get number of records
		index = 0
		numberRecords = len(data)

		while True:

			# check if there are no more records to insert
			if index > numberRecords or numberRecords == 0:
				break

			# execute query & commit
			# increment index to track rows to insert with chunking
			print("TEST")
			self.cursor.executemany(query, data[index:index + chunkSize])
			print("WOMP")
			self.connection.commit()
			index += chunkSize



	def insert(self, table, data, chunkSize=100):

		# get column names of table
		# dynamically create list of variable placeholders for dynamic SQL
		# dynamically create SQL
		columns = self.getAllColumnNames(table=table)
		columnVariables = len(columns) * ['%s']
		query = "INSERT INTO {} ({}) VALUES ({})".format(table, ', '.join(columns), ', '.join(columnVariables))
		self._chunkInsert(table=table, data=data, chunkSize=chunkSize, query=query)


	# Needs work to fix PostgreSQL + MySQL
	def append(self, table, data, chunkSize=100):

		# get column names of table
		allColumns, primaryKeyColumns, nonPrimaryKeyColumns = self._getColumnBuckets(table=table)

		# check if the target table only has primary keys and unique columns since it would not require the duplicate portion of the insert statement
		# create dynamic SQL
		if not primaryKeyColumns:
			self.insert(table=table, data=data, chunkSize=chunkSize)
		else:

			if self.type == 'mysql':
				duplicateColumnNames = [column + '=VALUES(' + column + ')' for column in nonPrimaryKeyColumns]
				columnVariables = len(allColumns) * ['%s']
				query = "INSERT INTO {} ({}) VALUES ({}) ON DUPLICATE KEY UPDATE {}".format(table, ', '.join(allColumns), ', '.join(columnVariables), ', '.join(duplicateColumnNames))
				self._chunkInsert(table=table, data=data, chunkSize=chunkSize, query=query)
			elif self.type == 'postgresql':
				print('test')
				allColumnVariables = len(allColumns) * ['%s']
				nonPrimaryKeyColumnVariables = len(nonPrimaryKeyColumns) * ['%s']
				print(nonPrimaryKeyColumnVariables)

				query = query="INSERT INTO {} ({}) VALUES ({}) ON CONFLICT({}) DO UPDATE SET ({})=({})".format(table, ', '.join(allColumns), ', '.join(allColumnVariables), ','.join(primaryKeyColumns), ', '.join(nonPrimaryKeyColumns), ','.join(nonPrimaryKeyColumnVariables))
				print(query)
				self.cursor.executemany(query, data)
				print("TESTICLE")


	# Needs work to fix PostgreSQL + MySQL
	def appendFromStage(self, targetTable, stageTable):

		# get table columns
		# get non-primary key columns
		columns = self.getAllColumnNames(table=targetTable)
		nonPrimaryKeyColumns= self.getNonPrimaryColumnNames(table=targetTable)

		# check if the target table only has primary keys and unique columns since it would not require the duplicate portion of the insert statement
		# create dynamic SQL
		if not nonPrimaryKeyColumns:
			query = "INSERT IGNORE INTO " + targetTable + " (" + ' ,'.join(columns) + ") SELECT " + ', '.join(columns) + " FROM " + stageTable
		else:

			duplicateColumnNames = [column + '=VALUES(' + column + ')' for column in nonPrimaryKeyColumns]

			if self.type == 'mysql':
				duplicateColumnNames = [column + '=VALUES(' + column + ')' for column in nonPrimaryKeyColumns]
				query = "INSERT INTO {} ({}) SELECT {} FROM {} ON DUPLICATE KEY UPDATE {}".format(targetTable, ', '.join(columns), ', '.join(columns), stageTable, ', '.join(duplicateColumnNames))
			elif self.type == 'postgresql':
				query = "PLACEHOLDER"

		# execute query & commit
		self.cursor.execute(query)
		self.connection.commit()

		query = "SELECT {} FROM {}".format(targetTable, ' ,'.join(columns))
		self.cursor.execute(query)


	def swap(self, targetTable, stageTable):

		# create temporary table to allow staging table to be renamed
		# create dynamic SQL
		tempTable = targetTable + '_tmp'

		if self.type == 'mysql':
			query = "RENAME TABLE {} TO {}, {} TO {}, {} TO {}".format(stageTable, tempTable, targetTable, stageTable, tempTable, targetTable)
		elif self.type == 'postgresql':
			query = "ALTER TABLE {} RENAME TO {}; ALTER TABLE {} RENAME TO {}; ALTER TABLE {} RENAME TO {}".format(stageTable, tempTable, targetTable, stageTable, tempTable, targetTable)

		# execute query & commit
		self.cursor.execute(query)
		self.connection.commit()
