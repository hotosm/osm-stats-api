# Copyright (C) 2021 Humanitarian OpenStreetmap Team

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# Humanitarian OpenStreetmap Team
# 1100 13th Street NW Suite 800 Washington, D.C. 20005
# <info@hotosm.org>

from psycopg2 import sql

HSTORE_COLUMN = "tags"


def create_hashtag_filter_query(project_ids, hashtags, cur, conn):
    '''returns hastag filter query '''

    merged_items = [*project_ids, *hashtags]

    filter_query = "({hstore_column} -> %s) ~~ %s"

    hashtag_filter_values = [
        *[f"%hotosm-project-{i} %" for i in project_ids],
        *[f"%{i} %" for i in hashtags],
    ]
    hashtag_tags_filters = [
        cur.mogrify(filter_query, ("hashtags", i)).decode()
        for i in hashtag_filter_values
    ]

    comment_filter_values = [
        *[f"%hotosm-project-{i};%" for i in project_ids],
        *[f"%{i};%" for i in hashtags],
    ]
    comment_tags_filters = [
        cur.mogrify(filter_query, ("comment", i)).decode()
        for i in comment_filter_values
    ]

    hashtag_filter = [*hashtag_tags_filters, *comment_tags_filters]

    hashtag_filter = [
        sql.SQL(f).format(hstore_column=sql.Identifier(HSTORE_COLUMN))
        for f in hashtag_filter
    ]

    hashtag_filter = sql.SQL(" OR ").join(hashtag_filter).as_string(conn)

    return hashtag_filter


def create_timestamp_filter_query(from_timestamp, to_timestamp, cur):
    '''returns timestamp filter query '''

    timestamp_column = "created_at"
    # Subquery to filter changesets matching hashtag and dates.
    timestamp_filter = sql.SQL("{timestamp_column} between %s AND %s").format(
        timestamp_column=sql.Identifier(timestamp_column))
    timestamp_filter = cur.mogrify(timestamp_filter,
                                   (from_timestamp, to_timestamp)).decode()

    return timestamp_filter


def create_changeset_query(params, conn, cur):
    '''returns the changeset query'''

    hashtag_filter = create_hashtag_filter_query(params.project_ids,
                                                 params.hashtags, cur, conn)
    timestamp_filter = create_timestamp_filter_query(params.from_timestamp,
                                                     params.to_timestamp, cur)

    changeset_query = f"""
    SELECT user_id, id as changeset_id, user_name as username
    FROM osm_changeset
    WHERE {timestamp_filter} AND ({hashtag_filter})
    """

    return changeset_query, hashtag_filter, timestamp_filter


def create_osm_history_query(changeset_query, with_username):
    '''returns osm history query'''

    column_names = [
        f"(each({HSTORE_COLUMN})).key AS feature",
        "action",
        "count(distinct id) AS count",
    ]
    group_by_names = ["feature", "action"]

    if with_username is True:
        column_names.append("username")
        group_by_names.extend(["user_id", "username"])

    order_by = (["count DESC"]
                if with_username is False else ["user_id", "action", "count"])
    order_by = ", ".join(order_by)

    columns = ", ".join(column_names)
    group_by_columns = ", ".join(group_by_names)

    query = f"""
    WITH T1 AS({changeset_query})
    SELECT {columns} FROM osm_element_history AS t2, t1
    WHERE t1.changeset_id = t2.changeset
    GROUP BY {group_by_columns} ORDER BY {order_by}
    """

    return query


def create_users_contributions_query(params, changeset_query):
    '''returns user contribution query'''

    project_ids = ",".join([str(p) for p in params.project_ids])
    from_timestamp = params.from_timestamp.isoformat()
    to_timestamp = params.to_timestamp.isoformat()

    query = f"""
    WITH T1 AS({changeset_query}),
    T2 AS (
        SELECT (each(tags)).key AS feature,
            user_id,
            username,
            count(distinct id) AS count
        FROM osm_element_history AS t2, t1
        WHERE t1.changeset_id    = t2.changeset
        GROUP BY feature, user_id, username
    ),
    T3 AS (
        SELECT user_id,
            username,
            SUM(count) AS total_buildings
        FROM T2
        WHERE feature = 'building'
        GROUP BY user_id, username
    )
    SELECT user_id,
        username,
        total_buildings,
        public.tasks_per_user(user_id,
            '{project_ids}',
            '{from_timestamp}',
            '{to_timestamp}',
            'MAPPED') AS mapped_tasks,
        public.tasks_per_user(user_id,
            '{project_ids}',
            '{from_timestamp}',
            '{to_timestamp}',
            'VALIDATED') AS validated_tasks,
        public.editors_per_user(user_id,
            '{from_timestamp}',
            '{to_timestamp}') AS editors
    FROM T3;
    """
    return query

def create_hashtagfilter_underpass(hashtags,columnname):
    """Generates hashtag filter query on the basis of list of hastags."""
    
    hashtag_filters = []
    for i in hashtags:
        
        hashtag_filters.append(f"'{i}'=ANY({columnname})")
   
    join_query = " OR ".join(hashtag_filters)
    returnquery = f"WHERE {join_query}"
    
    return returnquery

def generate_data_quality_query(params):
    '''returns data quality query with filters and parameteres provided'''
    print(params)
    hashtag_add_on="hotosm-project-"
    if "all" in params.issue_types:
        issue_types = ['badvalue','badgeom']
    else:
        issue_types=[]
        for p in params.issue_types:
            issue_types.append(str(p))
    
    change_ids=[]
    for p in params.project_ids:
        change_ids.append(hashtag_add_on+str(p)) 

    hashtagfilter=create_hashtagfilter_underpass(change_ids,"hashtags")
    status_filter=create_hashtagfilter_underpass(issue_types,"status")
    '''Geojson output query for pydantic model'''
    # query1 = """
    #     select '{ "type": "Feature","properties": {   "Osm_id": ' || osm_id ||',"Changeset_id":  ' || change_id ||',"Changeset_timestamp": "' || timestamp ||'","Issue_type": "' || cast(status as text) ||'"},"geometry": ' || ST_AsGeoJSON(location)||'}'
    #     FROM validation
    #     WHERE   status IN (%s) AND
    #             change_id IN (%s)
    # """ % (issue_types, change_ids)
    '''Normal Query to feed our OUTPUT Class '''
    query =f"""   with t1 as (
        select id
                From changesets 
                  {hashtagfilter}
            ),
        t2 AS (
             SELECT osm_id as Osm_id,
                change_id as Changeset_id,
                timestamp::text as Changeset_timestamp,
                status::text as Issue_type,
                ST_X(location::geometry) as lng,
                ST_Y(location::geometry) as lat

        FROM validation join t1 on change_id = t1.id
        {status_filter}
                )
        select *
        from t2
        """
    
   
    return query

