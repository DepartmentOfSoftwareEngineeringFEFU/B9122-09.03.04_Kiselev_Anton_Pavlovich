from io import StringIO
from typing import BinaryIO, Iterator

import pandas as pd


REQUIRED_COLUMNS = {
    "mmsi",
    "timestamp",
    "latitude",
    "longitude",
    "speed",
    "course",
    "vessel_type",
}


def _normalize_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    dataframe = dataframe.copy()
    dataframe.columns = [column.strip().lower() for column in dataframe.columns]

    missing_columns = REQUIRED_COLUMNS - set(dataframe.columns)
    if missing_columns:
        raise ValueError(
            f"В CSV-файле отсутствуют обязательные колонки: {', '.join(sorted(missing_columns))}"
        )

    return dataframe


def read_ais_csv(file_content: bytes) -> pd.DataFrame:
    """
    Чтение небольшого CSV-файла с АИС-данными.
    Оставлено для совместимости и тестовых файлов.
    """
    decoded_content = file_content.decode("utf-8-sig")
    dataframe = pd.read_csv(StringIO(decoded_content))
    return _normalize_columns(dataframe)


def clean_ais_data(dataframe: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Первичная обработка АИС-данных:
    - приведение типов;
    - удаление строк с некорректными координатами;
    - удаление строк с некорректной скоростью;
    - удаление дубликатов;
    - сортировка по MMSI и времени.
    """
    dataframe = _normalize_columns(dataframe)
    initial_rows = len(dataframe)

    dataframe = dataframe.copy()

    dataframe["mmsi"] = dataframe["mmsi"].astype(str).str.strip()
    dataframe["timestamp_utc"] = pd.to_datetime(
        dataframe["timestamp"],
        errors="coerce",
        utc=True,
    )

    dataframe["latitude"] = pd.to_numeric(dataframe["latitude"], errors="coerce")
    dataframe["longitude"] = pd.to_numeric(dataframe["longitude"], errors="coerce")
    dataframe["speed"] = pd.to_numeric(dataframe["speed"], errors="coerce")
    dataframe["course"] = pd.to_numeric(dataframe["course"], errors="coerce")
    dataframe["vessel_type"] = dataframe["vessel_type"].astype(str).str.strip()

    dataframe = dataframe.dropna(
        subset=["mmsi", "timestamp_utc", "latitude", "longitude"]
    )

    dataframe = dataframe[
        (dataframe["latitude"] >= -90)
        & (dataframe["latitude"] <= 90)
        & (dataframe["longitude"] >= -180)
        & (dataframe["longitude"] <= 180)
    ]

    dataframe = dataframe[
        (dataframe["speed"].isna())
        | ((dataframe["speed"] >= 0) & (dataframe["speed"] <= 60))
    ]

    dataframe = dataframe[
        (dataframe["course"].isna())
        | ((dataframe["course"] >= 0) & (dataframe["course"] < 360))
    ]

    before_duplicates = len(dataframe)

    dataframe = dataframe.drop_duplicates(
        subset=["mmsi", "timestamp_utc", "latitude", "longitude"]
    )

    dataframe = dataframe.sort_values(by=["mmsi", "timestamp_utc"])

    dataframe = dataframe[
        [
            "mmsi",
            "timestamp_utc",
            "latitude",
            "longitude",
            "speed",
            "course",
            "vessel_type",
        ]
    ]

    statistics = {
        "initial_rows": int(initial_rows),
        "valid_rows": int(len(dataframe)),
        "removed_rows": int(initial_rows - len(dataframe)),
        "removed_duplicates": int(before_duplicates - len(dataframe)),
    }

    return dataframe, statistics


def iter_clean_ais_csv_chunks(
    file_object: BinaryIO,
    chunksize: int = 100_000,
) -> Iterator[tuple[pd.DataFrame, dict]]:
    """
    Потоковое чтение и очистка большого CSV-файла.

    Используется для файлов большого объёма, чтобы не загружать весь CSV в память.
    """
    file_object.seek(0)

    for chunk in pd.read_csv(file_object, chunksize=chunksize, encoding="utf-8-sig"):
        cleaned_chunk, statistics = clean_ais_data(chunk)
        yield cleaned_chunk, statistics
