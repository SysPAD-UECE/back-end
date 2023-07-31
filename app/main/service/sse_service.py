import hashlib

import pandas as pd
from sqlalchemy import func, select, update

from app.main import db
from app.main.config import app_config
from app.main.model import Table, User
from app.main.service.global_service import (
    TableConnection,
    create_table_connection,
    get_cloud_database_url,
    get_primary_key_name,
)
from app.main.service.table_service import get_sensitive_columns, get_table

_batch_selection_size = app_config.BATCH_SELECTION_SIZE


def _calculate_progress(
    table: Table, number_row_selected: int, number_row_total: int
) -> None:
    table.anonymization_progress = (
        int((number_row_selected / number_row_total) * 50) + 50
    )
    db.session.commit()


def update_hash_column(
    cloud_table_connection: TableConnection,
    primary_key_name: str,
    primary_key_data: list,
    raw_data: list,
) -> None:
    for primary_key_value, row in zip(primary_key_data, range(raw_data.shape[0])):
        record = raw_data.iloc[row].values
        record = list(record)

        for index in range(len(record)):
            record[index] = str(record[index])

        new_record = str(record)

        hashed_line = hashlib.sha256(new_record.encode("utf-8")).hexdigest()

        statement = (
            update(cloud_table_connection.table)
            .where(
                cloud_table_connection.get_column(column_name=primary_key_name)
                == primary_key_value
            )
            .values(line_hash=hashed_line)
        )

        cloud_table_connection.session.execute(statement)

    cloud_table_connection.session.commit()


def generate_hash_rows(
    database_id: int, table_id: int, result_query: list[dict], current_user: User
) -> TableConnection:
    table = get_table(
        database_id=database_id, table_id=table_id, current_user=current_user
    )

    # Get primary key name of client database
    primary_key_name = get_primary_key_name(
        database_id=database_id, table_name=table.name
    )

    # Get sensitve columns of table
    client_columns_list = [primary_key_name] + get_sensitive_columns(
        database_id=database_id, table_id=table.id, current_user=current_user
    )["sensitive_column_names"]

    # Get cloud database url
    cloud_database_url = get_cloud_database_url(database_id=database_id)

    # Create cloud table connection
    cloud_table_connection = create_table_connection(
        database_url=cloud_database_url, table_name=table.name
    )

    # Transform query rows to dataframe
    raw_data = pd.DataFrame(data=result_query)[client_columns_list]
    primary_key_data = raw_data[primary_key_name]
    raw_data.pop(primary_key_name)

    update_hash_column(
        cloud_table_connection=cloud_table_connection,
        primary_key_name=primary_key_name,
        primary_key_data=primary_key_data,
        raw_data=raw_data,
    )

    return cloud_table_connection


def generate_hash_column(
    client_database_id: int,
    client_database_url: str,
    table: Table,
) -> TableConnection:
    # Get primary key name
    primary_key_name = get_primary_key_name(
        database_url=client_database_url, table_name=table.name
    )

    # Get column names to encrypt along with primary key name
    client_columns_list = [primary_key_name] + get_sensitive_columns(
        database_id=client_database_id, table_id=table.id
    )["sensitive_column_names"]

    # Create client table connection
    client_table_connection = create_table_connection(
        database_url=client_database_url,
        table_name=table.name,
        columns_list=client_columns_list,
    )

    cloud_database_url = get_cloud_database_url(database_id=client_database_id)

    # Create cloud table connection
    cloud_table_connection = create_table_connection(
        database_url=cloud_database_url, table_name=table.name
    )

    # Proxy to get data on batch
    results_proxy = client_table_connection.session.execute(
        select(client_table_connection.table)
    )

    # Getting rows database
    results = results_proxy.fetchmany(_batch_selection_size)

    # Start number row selected
    number_row_selected = 0

    # Get number row total
    number_row_total = (
        client_table_connection.session.query(func.count())
        .select_from(client_table_connection.table)
        .scalar()
    )

    # Generate hashs
    while results:
        from_db = []

        for result in results:
            from_db.append(dict(result))

        raw_data = pd.DataFrame(data=from_db)[client_columns_list]
        primary_key_data = raw_data[primary_key_name]
        raw_data.pop(primary_key_name)

        update_hash_column(
            cloud_table_connection=cloud_table_connection,
            primary_key_name=primary_key_name,
            primary_key_data=primary_key_data,
            raw_data=raw_data,
        )

        number_row_selected += _batch_selection_size

        _calculate_progress(
            table=table,
            number_row_selected=number_row_selected,
            number_row_total=number_row_total,
        )

        # Getting rows database
        results = results_proxy.fetchmany(_batch_selection_size)

    return cloud_table_connection
