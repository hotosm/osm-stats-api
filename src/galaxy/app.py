'''Main page contains class for database mapathon and funtion for error printing  '''

import sys, os
from psycopg2 import connect
from psycopg2.extras import DictCursor
from psycopg2 import OperationalError
from .validation.models import *
from .query_builder.builder import *
import pandas
from json import loads as json_loads
from geojson_pydantic import Point, features


def print_psycopg2_exception(err):
    """ 
    function that handles and parses psycopg2 exceptions
    """
    '''details_exception'''
    err_type, err_obj, traceback = sys.exc_info()
    line_num = traceback.tb_lineno
    # the connect() error
    print("\npsycopg2 ERROR:", err, "on line number:", line_num)
    print("psycopg2 traceback:", traceback, "-- type:", err_type)
    # psycopg2 extensions.Diagnostics object attribute
    print("\nextensions.Diagnostics:", err.diag)
    # pgcode and pgerror exceptions
    print("pgerror:", err.pgerror)
    print("pgcode:", err.pgcode, "\n")
    raise err


def check_for_json(result_str):
    """Check if the Payload is a JSON document

        Return: bool:
            True in case of success, False otherwise
        """
    try:
        r_json = json_loads(result_str)
        return True, r_json
    except Exception as e:
        return False, None


class Database:
    """ Database class is used to connect with your database , run query  and get result from it . It has all tests and validation inside class """
    def __init__(self, db_params):
        """Database class constructor"""

        self.db_params = db_params
        print('Database class object created...')

    def connect(self):
        """Database class instance method used to connect to database parameters with error printing"""

        try:
            self.conn = connect(**self.db_params)
            self.cur = self.conn.cursor(cursor_factory=DictCursor)
            print('Database connection has been Successful...')
            return self.conn, self.cur
        except OperationalError as err:
            """pass exception to function"""
            print_psycopg2_exception(err)
            # set the connection to 'None' in case of error
            self.conn = None

    def executequery(self, query):
        """ Function to execute query after connection """
        # Check if the connection was successful
        try:
            if self.conn != None:
                self.cursor = self.cur
                # catch exception for invalid SQL statement

                try:
                    self.cursor.execute(query)
                    try:
                        result = self.cursor.fetchall()
                        # print(result)
                        # result1=Output(query,self.conn).to_dict()
                        # print(result1)
                        return result
                    except:
                        return self.cursor.statusmessage
                except Exception as err:
                    print_psycopg2_exception(err)

                    # rollback the previous transaction before starting another
                    self.conn.rollback()
                # closing  cursor object to avoid memory leaks
                # cursor.close()
                # self.conn.close()
            else:
                print("Database is not connected")
        except Exception as err:
            print("Oops ! You forget to have connection first")
            raise err

    def close_conn(self):
        """function for clossing connection to avoid memory leaks"""

        # Check if the connection was successful
        try:
            if self.conn != None:
                if self.cursor:
                    self.cursor.close()
                    self.conn.close()
                    print("Connection closed")
        except Exception as err:
            raise err


class Mapathon:
    """Class for mapathon detail report and summary report this is the class that self connects to database and provide you summary and detail report."""

    #constructor
    def __init__(self, db_dict, parameters):
        self.database = Database(db_dict)
        self.con, self.cur = self.database.connect()
        #parameter validation using pydantic model
        self.params = MapathonRequestParams(**parameters)

    # Mapathon class instance method
    def get_summary(self):
        """Function to get summary of your mapathon event """

        changeset_query, hashtag_filter, timestamp_filter = create_changeset_query(
            self.params, self.con, self.cur)
        osm_history_query = create_osm_history_query(changeset_query,
                                                     with_username=False)
        # print(osm_history_query)
        result = self.database.executequery(osm_history_query)
        mapped_features = [MappedFeature(**r) for r in result]
        total_contributor_query = f"""
                SELECT COUNT(distinct user_id) as contributors_count
                FROM osm_changeset
                WHERE {timestamp_filter} AND ({hashtag_filter})
            """
        # print(osm_history_query.encode('utf-8'))

        total_contributors = self.database.executequery(
            total_contributor_query)
        report = MapathonSummary(total_contributors=total_contributors[0].get(
            "contributors_count", "None"),
                                 mapped_features=mapped_features)
        return report.json()

    def get_detailed_report(self):
        """Function to get detail report of your mapathon event. It includes individual user contribution"""

        changeset_query, _, _ = create_changeset_query(self.params, self.con,
                                                       self.cur)
        # History Query
        osm_history_query = create_osm_history_query(changeset_query,
                                                     with_username=True)
        result = self.database.executequery(osm_history_query)

        mapped_features = [MappedFeatureWithUser(**r) for r in result]
        # Contribution Query
        contributors_query = create_users_contributions_query(
            self.params, changeset_query)
        # print(contributors_query.encode('utf-8'))
        result = self.database.executequery(contributors_query)
        # contributors = parse_obj_as(List[MapathonContributor], result)
        contributors = [MapathonContributor(**r) for r in result]
        report = MapathonDetail(contributors=contributors,
                                mapped_features=mapped_features)
        # print(Output(osm_history_query,self.con).to_list())
        return report.json()


class Output:
    '''
    Class to convert sql query result to specific output format. It uses Pandas Dataframe
    Parameters:
        supports : list, dict , json and sql query string along with connection
    Returns:
        json,csv,dict,list,dataframe   
    '''
    def __init__(self, result, connection=None):
        """Constructor"""
        if isinstance(result, (list, dict)):
            print(type(result))
            try:
                self.dataframe = pandas.DataFrame(result)
            except Exception as err:
                raise err
        elif isinstance(result, str):
            check, r_json = check_for_json(result)
            if check is True:
                print("i am json")
                try:
                    self.dataframe = pandas.json_normalize(r_json)
                except Exception as err:
                    raise err
            else:
                if connection is not None:
                    try:
                        self.dataframe = pandas.read_sql_query(
                            result, connection)
                    except Exception as err:
                        raise err
                else:
                    raise ValueError("Connection is required for SQL Query")
        else:
            raise ValueError("Input type " + str(type(result)) +
                             " is not supported")

    def to_JSON(self):
        """Function to convert query result to JSON, Returns JSON"""
        js = self.dataframe.to_json(orient='records')
        return js

    def to_list(self):
        """Function to convert query result to list, Returns list"""

        result_list = self.dataframe.values.tolist()
        return result_list

    def to_dict(self):
        """Function to convert query result to dict, Returns dict"""
        dic = self.dataframe.to_dict(orient='records')
        return dic

    def to_CSV(self, output_file_path):
        """Function to return CSV data , takes output location string as input"""
        if os.path.isfile(output_file_path) is True:
            os.remove(output_file_path)
        try:
            self.dataframe.to_csv(output_file_path, encoding='utf-8')
            return "CSV: Generated"
        except Exception as err:
            raise err

    def dataframe(self):
        """Function to return panda's dataframe for advanced users"""
        return self.dataframe


class DataQuality:
    '''
    Class for data quality report this is the class that self connects to database and provide you detail report about data quality inside specific tasking manager project
    Parameters:
            “project_ids”:[],
            “issue_type”: ["bad_geometry", "bad_value", "incomplete_tags", "all"] 
    Returns:
            JSON    
    '''

    # def __init__(self, db_dict, parameters):
    #     self.database = Database(db_dict)
    #     self.con, self.cur = self.database.connect()
    #     #parameter validation using pydantic model
    #     self.params = DataQualityRequestParams(**parameters)

    def __init__(self, db_dict):
        self.db = Database(db_dict)
        self.con, self.cur = self.db.connect()

    def get_report(self):
        query = f"""
                SELECT 
                    ST_AsGeoJSON(location) as geometry,
                    osm_id as Osm_id,
                    change_id as Changeset_id,
                    timestamp as Changeset_timestamp,
                    status as Issue_type
                FROM validation
                LIMIT 1
            """
        result=self.db.executequery(query)
        print(result)
        query_result = [{
            "properties": {
                "Osm_id": 1100,
                "Changeset_id": 1500,
                "Changeset_timestamp": "2021-08-27T9:00:00",
                "Issue_type": "bad_geometry",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [83.81469726562499, 28.24]
            }
        }, {
            "properties": {
                "Osm_id": 1100,
                "Changeset_id": 1500,
                "Changeset_timestamp": "2021-08-27T9:00:00",
                "Issue_type": "bad_geometry",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [83.81469726562499, 28.34]
            }
        }]

        dataquality_point = [
            DataQualityPointFeature(**p) for p in query_result
        ]
        dataquality_coll = DataQualityPointCollection(
            features=dataquality_point)
        print(dataquality_coll.json())
