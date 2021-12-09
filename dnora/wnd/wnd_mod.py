import xarray as xr
import numpy as np
from copy import copy
import pandas as pd
import sys
import re

# Import abstract classes and needed instances of them
from .read import ForcingReader
from .write import ForcingWriter

# Import default values and auxiliry functions
from .. import msg
from ..aux import day_list, create_filename_obj, create_filename_time, clean_filename, check_if_folder
from ..defaults import dflt_frc, list_of_placeholders

class Forcing:
    def __init__(self, grid, name='AnonymousForcing'):
        self.grid = copy(grid)
        self._name = copy(name)
        return

    def import_forcing(self, start_time: str, end_time: str, forcing_reader: ForcingReader, expansion_factor: float=1.2):
        """Imports forcing data from a certain source.

        Data are import between start_time and end_time from the source
        defined in the forcing_reader. Data are read around an area defined
        by the Grid object passed at initialization of this object.
        """

        self.start_time = copy(start_time)
        self.end_time = copy(end_time)

        msg.header(forcing_reader, "Loading wind forcing...")
        self.data = forcing_reader(
            self.grid, start_time, end_time, expansion_factor)

        return

    def export_forcing(self, forcing_writer: ForcingWriter, out_format: str=None, filestring: str=None, datestring: str=None, folder: str=None) -> None:
        """Exports the forcing data to a file.

        The forcing_writer defines the file format.
        """
        msg.header(forcing_writer, f"Writing wind forcing from {self.name()}")


        if out_format is None:
            out_format = forcing_writer._preferred_format()

        if filestring is None:
            filestring=dflt_frc['fs'][out_format]

        if datestring is None:
            datestring=dflt_frc['ds'][out_format]

        filename = self.filename(filestring=filestring, datestring=datestring)

        if folder is not None:
            folder = self.filename(filestring=folder)
        else:
            folder = self.filename(filestring=dflt_frc['fldr'][out_format])

        existed = check_if_folder(folder=folder, create=True)
        if not existed:
            msg.plain(f"Creating folder {folder}")

        output_files, output_folder = forcing_writer(self, filename=filename, folder=folder)

        return output_files, output_folder

    def filename(self, filestring: str=dflt_frc['fs']['General'], datestring: str=dflt_frc['ds']['General'], defaults: str=''):
        """Creates a filename for the object.

        The filename can be based on e.g. the name of the Grid or Boundary
        object itself, or the start and end times.

        This is typically called by a ForcingWriter object when using
        the .export_forcing() method.
        """

        # E.g. defaults='SWAN' uses all SWAN defaults
        if defaults:
            filestring = dflt_frc['fs'][defaults]
            datestring = dflt_frc['ds'][defaults]
            extension = dflt_frc['ext'][defaults]

        # Substitute placeholders for objects ($Grid etc.)
        filename = create_filename_obj(filestring=filestring, objects=[self, self.grid])
        # Substitute placeholders for times ($T0 etc.)
        filename = create_filename_time(filestring=filename, times=[self.start_time, self.end_time], datestring=datestring)

        return filename

    def folder(self, folderstring: str=dflt_frc['fldr']['General'], datestring: str=dflt_frc['ds']['General']) -> str:
        # Substitute placeholders for $Grid
        folder = create_filename_obj(filestring=folderstring, objects=[self.grid, self])
        folder = create_filename_time(filestring=folder, times=[self.start_time, self.end_time], datestring=datestring)
        folder = clean_filename(folder, list_of_placeholders)

        return folder


    def days(self):
        """Determins a Pandas data range of all the days in the time span."""

        days = day_list(start_time=self.start_time, end_time=self.end_time)
        return days

    def name(self) -> str:
        """Return the name of the grid (set at initialization)."""

        return copy(self._name)

    def time(self):
        return copy(pd.to_datetime(self.data.time.values))

    def dt(self) -> float:
        """ Returns time step of forcing data in hours."""
        return self.time().to_series().diff().dt.total_seconds().values[-1]/3600

    def u(self):
        return copy(self.data.u.values)

    def v(self):
        return copy(self.data.v.values)

    def nx(self):
        return (self.data.u.shape[2])

    def ny(self):
        return (self.data.u.shape[1])

    def nt(self):
        return (self.data.u.shape[0])

    def lon(self):
        """Returns a longitude vector of the grid."""

        if hasattr(self.data, 'lon'):
            lon = copy(self.data.lon.values)
        else:
            lon = np.array([])
        return lon

    def lat(self):
        """Returns a latitude vector of the grid."""

        if hasattr(self.data, 'lat'):
            lat = copy(self.data.lat.values)
        else:
            lat = np.array([])
        return lat

    def size(self) -> tuple:
        """Returns the size (nx, ny) of the grid."""

        return self.data.u.shape

    def _point_list(self, mask):
        """Provides a list on longitudes and latitudes with a given mask.

        Used to e.g. generate list of boundary points or land points.
        """

        meshlon, meshlat=np.meshgrid(self.lon(),self.lat())
        lonlat_flat = np.column_stack((meshlon.ravel(),meshlat.ravel()))
        mask_flat = mask.ravel()

        return lonlat_flat[mask_flat]


    def slice_data(self, start_time: str='', end_time: str=''):
        """Slice data in time. Returns an xarray dataset."""

        if not start_time:
            # This is not a string, but slicing works also with this input
            start_time = self.time()[0]

        if not end_time:
            # This is not a string, but slicing works also with this input
            end_time = self.time()[-1]

        sliced_data = self.data.sel(time=slice(start_time, end_time))

        return sliced_data

    def times_in_day(self, day):
        """Determines time stamps of one given day."""

        t0 = day.strftime('%Y-%m-%d') + "T00:00:00"
        t1 = day.strftime('%Y-%m-%d') + "T23:59:59"

        times = self.slice_data(start_time=t0, end_time=t1).time.values
        return times