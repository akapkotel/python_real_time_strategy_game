import os
import pathlib
from typing import Optional, Union

from utils.functions import find_paths_to_all_files_of_type
from utils.game_logging import log


class ResourcesManager:
    """
    This class finds paths to all audio files and textures used in game and caches them in internal dict for easy and
    fast access. Later on instead of searching a texture each time, when a new gameObject is instantiated, its
    constructor just query this manager for the proper path to the file.
    """

    def __init__(self, extensions: tuple[str] = ('png', 'wav'), resources_path: Optional[str] = None):
        self.extensions = extensions
        self.resources_path = resources_path or os.path.abspath('resources')
        self.resources = {}
        for extension in self.extensions:
            names_to_paths = find_paths_to_all_files_of_type(extension, self.resources_path)
            self.resources[extension] = {name: pathlib.Path(path, name) for name, path in names_to_paths.items()}
        log(f'ResourceManager found {sum(len(paths) for paths in self.resources.values())} files.', console=True)

    def get(self, file_name_or_extension: str) -> Union[str, dict[str, str]]:
        """
        Fetch a full path to the single game file (texture, sound, etc.) providing the name of this file, or paths to
        all files of a particular type by providing the extension only.
        """
        if file_name_or_extension in self.extensions:
            return self._get_paths_to_all_files_of_type(extension=file_name_or_extension)
        return self._get_path_to_single_file(file_name=file_name_or_extension)

    def _get_path_to_single_file(self, file_name: str) -> Union[dict[str, str], str]:
        extension = file_name.split('.')[-1]
        try:
            return self.resources[extension][file_name]
        except KeyError:
            raise FileNotFoundError(f'File {file_name} was not found in {self.resources_path} and its subdirectories!')

    def _get_paths_to_all_files_of_type(self, extension: str):
            try:
                return self.resources[extension]
            except KeyError:
                raise FileNotFoundError(f'There are no files with {extension} extensions in {self.resources_path}!')
