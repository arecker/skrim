import pathlib
import xml.etree.ElementTree


def load_fomod_config(temp_dir, paths):
    """Returns a parsed fomod config if the mod has one.

    Returns None if there is none."""

    fomod_paths = [p for p in paths if p.name.lower() == 'moduleconfig.xml' and len(p.parts) >= 2 and p.parts[-2].lower() == 'fomod']

    if not fomod_paths:
        return None

    data = (temp_dir / fomod_paths[0]).read_bytes()

    if data.startswith(b'\xff\xfe'):
        text = data.decode('utf-16-le')
    elif data.startswith(b'\xfe\xff'):
        text = data.decode('utf-16-be')
    elif data.startswith(b'\xef\xbb\xbf'):
        text = data.decode('utf-8-sig')
    else:
        text = data.decode('utf-8')

    return xml.etree.ElementTree.fromstring(text)


def recommended_plugin_index(plugins, skyrim_version):
    """Guess which plugin (1-indexed) a fomod group's own gameDependency patterns recommend.

    Returns None if we don't have a skyrim_version, or nothing recommends itself.
    """

    if skyrim_version is None:
        return None

    detected = tuple(int(part) for part in skyrim_version.split('.'))

    best_index = None
    best_threshold = None

    for i, plugin in enumerate(plugins, start=1):
        applicable = []
        for pattern in plugin.findall('./typeDescriptor/dependencyType/patterns/pattern'):
            game_dependency = pattern.find('./dependencies/gameDependency')
            if game_dependency is None:
                continue

            threshold = tuple(int(part) for part in game_dependency.attrib['version'].split('.'))
            if detected >= threshold:
                applicable.append((threshold, pattern.find('./type').attrib['name']))

        if not applicable:
            continue

        threshold, type_name = max(applicable, key=lambda pair: pair[0])
        if type_name == 'Recommended' and (best_threshold is None or threshold > best_threshold):
            best_index = i
            best_threshold = threshold

    return best_index


def installed_plugin_files(game_dir):
    """Return the lowercased plugin filenames (.esp/.esm/.esl) already sitting in game_dir's Data folder.

    Used to evaluate fomod <fileDependency> conditions during install. skrim always enables
    every plugin it installs (see toggle_plugins_file), so there's no separate 'inactive but
    present' state to track -- a plugin's presence on disk is enough to answer both the 'Active'
    and 'Inactive' fileDependency states correctly.
    """

    data_dir = pathlib.Path(game_dir) / 'Data'
    if not data_dir.is_dir():
        return frozenset()

    return frozenset(p.name.lower() for p in data_dir.iterdir() if p.suffix.lower() in ('.esp', '.esm', '.esl'))


def fomod_dependencies_met(dependencies, flags, data_files=frozenset()):
    """Evaluate a fomod <dependencies> element against a flags dict and installed plugin files.

    Handles flagDependency and fileDependency children, in document order, plus nested
    <dependencies> for compound conditions -- fomod authors mix these freely. gameDependency is
    treated as always satisfied, since skrim already gates the whole run on the detected Skyrim
    version rather than per-dependency.

    A flag that was never set by a chosen plugin counts as 'Off', matching how FOMOD authors use it.
    """

    results = []
    for dep in dependencies:
        if dep.tag == 'flagDependency':
            current = flags.get(dep.attrib['flag'], '')
            expected = dep.attrib['value']
            results.append(current == expected or (expected == 'Off' and current == ''))
        elif dep.tag == 'fileDependency':
            present = dep.attrib['file'].lower() in data_files
            results.append(not present if dep.attrib['state'] == 'Missing' else present)
        elif dep.tag == 'gameDependency':
            results.append(True)
        elif dep.tag == 'dependencies':
            results.append(fomod_dependencies_met(dep, flags, data_files))

    return all(results) if dependencies.attrib.get('operator', 'And') == 'And' else any(results)


def resolve_plugin_type(plugin, flags, data_files):
    """Resolve a fomod plugin's type (Required/Recommended/Optional/NotUsable/CouldBeUsable).

    Checks the plugin's typeDescriptor patterns (in order) against the current flags and
    installed files, falling back to its defaultType. Falls back further to 'Optional' for
    plugins with no typeDescriptor info at all, which keeps old two-state (visible/hidden) fomods
    behaving exactly as before.
    """

    static_type = plugin.find('./typeDescriptor/type')
    if static_type is not None:
        return static_type.attrib['name']

    dependency_type = plugin.find('./typeDescriptor/dependencyType')
    if dependency_type is None:
        return 'Optional'

    for pattern in dependency_type.findall('./patterns/pattern'):
        dependencies = pattern.find('./dependencies')
        if dependencies is not None and fomod_dependencies_met(dependencies, flags, data_files):
            return pattern.find('./type').attrib['name']

    default_type = dependency_type.find('./defaultType')
    return default_type.attrib['name'] if default_type is not None else 'Optional'


def calculate_fomod_choices(fomod_config, old_choices, skyrim_version=None, game_dir=None):
    """Prompt for (or reuse) a choice per fomod group.

    Returns a dict of group name -> chosen plugin name.
    """

    old_choices = old_choices or {}
    new_choices = {}
    flags = {}
    data_files = installed_plugin_files(game_dir) if game_dir else frozenset()

    for step in fomod_config.findall('./installSteps/installStep'):
        visible = step.find('./visible/dependencies')
        if visible is not None and not fomod_dependencies_met(visible, flags, data_files):
            continue

        for group in step.findall('./optionalFileGroups/group'):
            group_type = group.attrib['type']
            if group_type not in ('SelectExactlyOne', 'SelectAny', 'SelectAtMostOne', 'SelectAll'):
                raise NotImplementedError(f'fomod group type not supported yet: {group_type}')

            group_name = group.attrib['name']
            plugins = group.findall('./plugins/plugin')
            plugin_names = [plugin.attrib['name'] for plugin in plugins]

            if group_type == 'SelectAll':
                chosen = plugin_names

            elif group_type in ('SelectAny', 'SelectAtMostOne'):
                limit = 1 if group_type == 'SelectAtMostOne' else len(plugins)

                remembered = old_choices.get(group_name)
                if isinstance(remembered, list) and len(remembered) <= limit and all(name in plugin_names for name in remembered):
                    chosen = remembered
                else:
                    # a plugin's typeDescriptor tells us whether it even applies to this
                    # install (NotUsable) and whether it should be pre-picked (Required/
                    # Recommended) -- e.g. Legacy of the Dragonborn's patches fomod has groups
                    # with 50+ plugins, one per compatible mod, and almost all of them resolve
                    # to NotUsable because that mod isn't installed. Filtering those out turns a
                    # wall of irrelevant prompts into a short, mostly-defaultable one.
                    plugin_types = {plugin.attrib['name']: resolve_plugin_type(plugin, flags, data_files) for plugin in plugins}
                    available = [plugin for plugin in plugins if plugin_types[plugin.attrib['name']] != 'NotUsable']
                    defaults = [plugin.attrib['name'] for plugin in available if plugin_types[plugin.attrib['name']] in ('Required', 'Recommended')]

                    if group_type == 'SelectAtMostOne' and len(defaults) > 1:
                        # can't default multiple picks into a one-choice slot; let the user decide
                        defaults = []

                    if not available:
                        chosen = []
                    else:
                        label = 'select at most one' if group_type == 'SelectAtMostOne' else 'select any'
                        print(f'\n{group_name} ({label}):')
                        for i, plugin in enumerate(available, start=1):
                            description = plugin.findtext('description', default='').strip()
                            marker = ' (recommended)' if plugin.attrib['name'] in defaults else ''
                            print(f'  {i}) {plugin.attrib["name"]}{marker}')
                            if description:
                                print(f'     {description}')

                        default_prompt = f'default {", ".join(defaults)}' if defaults else 'blank for none'
                        while True:
                            choice = input(f'Choices [1-{len(available)}, comma-separated, {default_prompt}]: ').strip()
                            if not choice:
                                picks = list(defaults)
                                break

                            indices = [part.strip() for part in choice.split(',')]
                            if len(indices) <= limit and all(index.isdigit() and 1 <= int(index) <= len(available) for index in indices):
                                picks = [available[int(index) - 1].attrib['name'] for index in indices]
                                break

                            if group_type == 'SelectAtMostOne':
                                print(f'Please enter at most one number between 1 and {len(available)}.')
                            else:
                                print(f'Please enter numbers between 1 and {len(available)}, comma-separated.')

                        chosen = picks

            else:
                remembered = old_choices.get(group_name)
                if remembered in plugin_names:
                    chosen = remembered
                else:
                    plugin_types = {plugin.attrib['name']: resolve_plugin_type(plugin, flags, data_files) for plugin in plugins}
                    type_recommended = [i for i, plugin in enumerate(plugins, start=1) if plugin_types[plugin.attrib['name']] in ('Required', 'Recommended')]
                    default_index = type_recommended[0] if len(type_recommended) == 1 else recommended_plugin_index(plugins, skyrim_version)

                    print(f'\n{group_name}:')
                    for i, plugin in enumerate(plugins, start=1):
                        description = plugin.findtext('description', default='').strip()
                        marker = ' (default)' if i == default_index else ''
                        print(f'  {i}) {plugin.attrib["name"]}{marker}')
                        if description:
                            print(f'     {description}')

                    prompt = f'Choice [1-{len(plugins)}]'
                    if default_index is not None:
                        prompt += f', default {default_index}'
                    prompt += ': '

                    while True:
                        choice = input(prompt).strip()
                        if not choice and default_index is not None:
                            choice = str(default_index)

                        if choice.isdigit() and 1 <= int(choice) <= len(plugins):
                            break

                        print(f'Please enter a number between 1 and {len(plugins)}.')

                    chosen = plugins[int(choice) - 1].attrib['name']

            new_choices[group_name] = chosen

            chosen_set = set(chosen) if isinstance(chosen, list) else {chosen}
            for plugin in plugins:
                if plugin.attrib['name'] in chosen_set:
                    for flag in plugin.findall('./conditionFlags/flag'):
                        flags[flag.attrib['name']] = (flag.text or '').strip()

    return new_choices


def calculate_fomod_targets(fomod_config, choices, paths, game_dir=None):
    """Take a parsed fomod config, chosen plugin names, and relative paths.

    Returns a list of src/dst pairs.
    """

    def matched(source, destination):
        source_parts = tuple(part.lower() for part in pathlib.Path(source.replace('\\', '/')).parts)
        dest_parts = pathlib.Path(destination.replace('\\', '/')).parts if destination else ()

        pairs = []
        for p in paths:
            p_parts_lower = tuple(part.lower() for part in p.parts)
            if p_parts_lower[:len(source_parts)] != source_parts:
                continue
            pairs.append((p, pathlib.Path('Data', *dest_parts, *p.parts[len(source_parts):])))
        return pairs

    def matched_file(source, destination):
        source_parts = tuple(part.lower() for part in pathlib.Path(source.replace('\\', '/')).parts)
        dest_parts = pathlib.Path(destination.replace('\\', '/')).parts if destination else source_parts

        for p in paths:
            if tuple(part.lower() for part in p.parts) == source_parts:
                return [(p, pathlib.Path('Data', *dest_parts))]
        return []

    targets = []
    flags = {}
    data_files = installed_plugin_files(game_dir) if game_dir else frozenset()

    for folder in fomod_config.findall('./requiredInstallFiles/folder'):
        targets += matched(folder.attrib['source'], folder.attrib.get('destination', ''))

    for file in fomod_config.findall('./requiredInstallFiles/file'):
        targets += matched_file(file.attrib['source'], file.attrib.get('destination', ''))

    for step in fomod_config.findall('./installSteps/installStep'):
        visible = step.find('./visible/dependencies')
        if visible is not None and not fomod_dependencies_met(visible, flags, data_files):
            continue

        for group in step.findall('./optionalFileGroups/group'):
            group_name = group.attrib['name']
            chosen = choices[group_name]
            chosen_names = chosen if isinstance(chosen, list) else [chosen]
            chosen_plugins = [plugin for plugin in group.findall('./plugins/plugin') if plugin.attrib['name'] in chosen_names]

            for chosen_plugin in chosen_plugins:
                for folder in chosen_plugin.findall('./files/folder'):
                    targets += matched(folder.attrib['source'], folder.attrib.get('destination', ''))

                for file in chosen_plugin.findall('./files/file'):
                    targets += matched_file(file.attrib['source'], file.attrib.get('destination', ''))

                for flag in chosen_plugin.findall('./conditionFlags/flag'):
                    flags[flag.attrib['name']] = (flag.text or '').strip()

    for pattern in fomod_config.findall('./conditionalFileInstalls/patterns/pattern'):
        dependencies = pattern.find('./dependencies')
        if dependencies is None or not fomod_dependencies_met(dependencies, flags, data_files):
            continue

        for folder in pattern.findall('./files/folder'):
            targets += matched(folder.attrib['source'], folder.attrib.get('destination', ''))

        for file in pattern.findall('./files/file'):
            targets += matched_file(file.attrib['source'], file.attrib.get('destination', ''))

    return targets
