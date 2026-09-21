import collections
import configparser
import pathlib

# The [skrim] section of the config file.
Config = collections.namedtuple('Config', [
    'downloads_dir',
    'game_dir',
    'plugins_file',
    'ini_file',
])

# A Mod that is ready to be installed from a downloaded package.
Mod = collections.namedtuple('Mod', [
    'name',
    'filename',
    'requires',
])


def load_config(config_path):
    """Load the `[skrim]` section and the list of `Mod` tuples from the config path.

    Raises a ValueError if you dicked up, like passed in a path that
    doesn't exist or screwed up your config file.  Take it up with
    python, I'm just using the library!

    Raises a ValueError if [skrim] is missing or any of its fields are missing.

    Returns a (Config, list of Mod) tuple.
    """
    config_path = pathlib.Path(config_path)

    if not config_path.is_file():
        raise ValueError(f'config file does not exist: {config_path}')

    parser = configparser.ConfigParser()

    try:
        parser.read(config_path)
    except configparser.Error as error:
        raise ValueError(f'failed to parse config file {config_path}: {error}') from error

    if not parser.has_section('skrim'):
        raise ValueError(f'[skrim] section missing from {config_path}')

    try:
        config = Config(**dict(parser.items('skrim')))
    except TypeError as e:
        raise ValueError(f'[skrim] is misconfigured! {e}')

    config = config._replace(
        downloads_dir=pathlib.Path(config.downloads_dir).expanduser(),
        game_dir=pathlib.Path(config.game_dir).expanduser().resolve(),
        plugins_file=pathlib.Path(config.plugins_file).expanduser().resolve(),
        ini_file=pathlib.Path(config.ini_file).expanduser().resolve(),
    )

    mods = []

    for section in parser.sections():
        if section == 'skrim':
            continue

        kwargs = dict(parser.items(section))
        requires = tuple(name.strip() for name in kwargs.pop('requires', '').split(',') if name.strip())

        try:
            mod = Mod(name=section, requires=requires, **kwargs)
        except TypeError as e:
            raise ValueError(f'[{section}] is misconfigured! {e}')

        mod_path = config.downloads_dir / mod.filename
        if not mod_path.is_file():
            raise ValueError(f'[{section}] file does not exist: {mod_path}')

        mods.append(mod)

    validate_requirements(mods)

    return config, mods


def validate_requirements(mods):
    """Check that each mod's `requires` entries exist and precede it in `mods`.

    Raises a ValueError on a missing or out-of-order dependency.
    """
    mod_index_by_name = {mod.name: i for i, mod in enumerate(mods)}

    for i, mod in enumerate(mods):
        for required_name in mod.requires:
            required_index = mod_index_by_name.get(required_name)
            if required_index is None:
                raise ValueError(f'[{mod.name}] requires [{required_name}], which is not in config')
            if required_index > i:
                raise ValueError(f'[{mod.name}] requires [{required_name}], which is listed after it in config')
