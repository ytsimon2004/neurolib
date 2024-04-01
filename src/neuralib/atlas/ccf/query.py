from __future__ import annotations

import attrs
import polars as pl
from typing_extensions import Self, Final, final

from neuralib.atlas.ccf.classifier import supply_overlap_dataframe
from neuralib.atlas.type import Source, Area
from neuralib.atlas.util import get_margin_merge_level

__all__ = ['RoiAreaQuery', 'SubregionResult']


@final
class RoiAreaQuery:

    def __init__(self,
                 parsed_df: pl.DataFrame,
                 area: Area,
                 source_order: tuple[Source, ...] | None = None):
        """
        Find a subset of rois from a specific area
        :param parsed_df: parsed dataframe from ccf pipeline
        :param area: area name
        :param source_order:
        """

        self.parsed_df: Final[pl.DataFrame] = parsed_df
        self.area: Final[Area] = area

        if source_order is None:
            self.source_order = tuple(self.parsed_df['source'].unique().to_list())
        else:
            self.source_order = source_order

        self._query_col = get_margin_merge_level(self.parsed_df, self.area, 'lowest')
        self._show_col: str | None = None  # infer after query
        self.query_result: Final[pl.DataFrame] = self.hierarchical_query()

    def __repr__(self):
        q = f'Query -> {self.query_col}'
        s = f'Show -> {self.show_col}'
        res = self.query_result.select('name', self.query_col, self.show_col)
        return '\n'.join([q, s, str(res)])

    @classmethod
    def by(cls, df: pl.DataFrame,
           area: Area,
           source_order: tuple[Source, ...] | None = None) -> Self:

        return RoiAreaQuery(df, area, source_order)

    @property
    def query_col(self) -> str:
        return self._query_col

    @property
    def show_col(self) -> str:
        return self._show_col

    def hierarchical_query(self) -> pl.DataFrame:
        """Get the query dataframe
        Auto infer query col & show_col based on area name"""
        if self._show_col is None:
            highest_lv = int(get_margin_merge_level(self.parsed_df, self.area, 'highest').split('_')[-1])
            self._show_col = f'merge_ac_{highest_lv + 1}'

            if self._show_col not in self.parsed_df.columns:
                self._show_col = 'acronym'

        return self.parsed_df.filter(pl.col(self.query_col) == self.area)

    def get_subregion_result(self, unit: str,
                             supply_overlap: bool = True) -> SubregionResult:

        dat = self.query_result.select(['source', self.show_col])

        if supply_overlap:
            dat = supply_overlap_dataframe(dat)

        df = (dat.group_by(['source', self.show_col])
              .agg(pl.col(self.show_col).count().alias('n_rois'))
              .with_columns((pl.col('n_rois') / pl.col('n_rois').sum().over('source') * 100).alias('percent'))
              .sort('percent', descending=True))

        idx = {val: idx for idx, val in enumerate(self.source_order)}
        ch_sort = pl.col('source').replace(idx)

        #
        numbers = df.group_by('source').agg(pl.col('n_rois').sum())
        numbers = numbers.sort(ch_sort)

        ch_count_all = self.parsed_df.group_by('source').len()
        roi_profile = (numbers.join(ch_count_all, on='source')
                       .with_columns((pl.col('n_rois') / pl.col('len')).alias('total_perc'))
                       .sort(ch_sort))
        #
        df = (df.pivot(columns=self._show_col, index='source', values=unit, aggregate_function='first')
              .fill_null(0))

        df = df.sort(ch_sort)

        return SubregionResult(self, unit, df, roi_profile)


@attrs.define
class SubregionResult:
    source_query: RoiAreaQuery

    unit: str = attrs.field(validator=attrs.validators.in_(('n_rois', 'percent')))
    """Note that percent are normalized by queried dataframe"""

    data: pl.DataFrame
    """
    * Optional with animal col
    ┌─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬────────┐
    │ source  ┆ VISam   ┆ VISp    ┆ VISpm   ┆ VISl    ┆ VISal   ┆ VISpor  ┆ VISli   ┆ VISpl   ┆ VISC   │
    │ ---     ┆ ---     ┆ ---     ┆ ---     ┆ ---     ┆ ---     ┆ ---     ┆ ---     ┆ ---     ┆ ---    │
    │ str     ┆ f64     ┆ f64     ┆ f64     ┆ f64     ┆ f64     ┆ f64     ┆ f64     ┆ f64     ┆ f64    │
    ╞═════════╪═════════╪═════════╪═════════╪═════════╪═════════╪═════════╪═════════╪═════════╪════════╡
    │ aRSC    ┆ 25.4669 ┆ 34.0318 ┆ 23.0979 ┆ 6.42369 ┆ 6.37813 ┆ 1.77676 ┆ 2.27790 ┆ 0.0     ┆ 0.5466 │
    │         ┆ 7       ┆ 91      ┆ 5       ┆         ┆ 2       ┆ 5       ┆ 4       ┆         ┆ 97     │
    │ pRSC    ┆ 15.1445 ┆ 36.1079 ┆ 29.5568 ┆ 10.7129 ┆ 3.04431 ┆ 2.38921 ┆ 1.92678 ┆ 1.07899 ┆ 0.0385 │
    │         ┆ 09      ┆         ┆ 4       ┆ 09      ┆ 6       ┆         ┆ 2       ┆ 8       ┆ 36     │
    │ overlap ┆ 48.5294 ┆ 8.82352 ┆ 31.25   ┆ 4.04411 ┆ 3.30882 ┆ 2.57352 ┆ 1.10294 ┆ 0.0     ┆ 0.3676 │
    │         ┆ 12      ┆ 9       ┆         ┆ 8       ┆ 4       ┆ 9       ┆ 1       ┆         ┆ 47     │
    └─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴────────┘
    """

    roi_profile: pl.DataFrame
    """
    ┌─────────┬────────┬───────┬────────────┐
    │ source  ┆ n_rois ┆ count ┆ total_perc │
    │ ---     ┆ ---    ┆ ---   ┆ ---        │
    │ str     ┆ u32    ┆ u32   ┆ f64        │
    ╞═════════╪════════╪═══════╪════════════╡
    │ aRSC    ┆ 899    ┆ 11403 ┆ 0.078839   │
    │ pRSC    ┆ 6744   ┆ 26280 ┆ 0.256621   │
    │ overlap ┆ 225    ┆ 3470  ┆ 0.064841   │
    └─────────┴────────┴───────┴────────────┘
    """

    def del_overlap(self) -> Self:
        """keep same `source_query` but delete the `overlap` data and roi_profile"""
        expr = pl.col('source') != 'overlap'
        dat = self.data.filter(expr)
        profile = self.roi_profile.filter(expr)
        return attrs.evolve(self, data=dat, roi_profile=profile)

    def with_animal(self, animal: str) -> Self:
        """add animal col for batch/statistic purpose"""
        data = self.data.with_columns(pl.lit(animal).alias('animal'))
        return attrs.evolve(self, data=data)

    @property
    def sources(self) -> list[Source]:
        return self.data['source'].to_list()

    @property
    def channel_weight(self) -> pl.DataFrame:
        """foreach channel fraction  in all rois"""
        return self.roi_profile.drop('n_rois', 'count')

    @property
    def weight_list(self) -> list[float]:
        return self.channel_weight.get_column('total_perc').to_list()

    @property
    def values(self) -> pl.DataFrame:
        return self.data.select(pl.exclude('source'))

    @property
    def areas(self) -> list[Area]:
        return self.values.columns

    @property
    def n_areas(self) -> int:
        return len(self.areas)

    @property
    def n_rois_info(self) -> list[str]:
        """for plotting"""
        return [
            f'{self.source_query.area} -> {row[0]}: {row[1]} ({round(self.weight_list[i], 3)})'
            for i, row in enumerate(self.roi_profile.iter_rows())
        ]
