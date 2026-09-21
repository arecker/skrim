"""Unit tests for skrim's fomod handling (calculate_fomod_choices, calculate_fomod_targets, and friends)."""

import pathlib
import tempfile
import unittest
import unittest.mock
import xml.etree.ElementTree

import skrim.fomod as skrim


def fomod_xml(text):
    return xml.etree.ElementTree.fromstring(text)


class TestFomodDependenciesMet(unittest.TestCase):

    def test_and_operator_requires_every_flag(self):
        dependencies = fomod_xml('''
            <dependencies operator="And">
                <flagDependency flag="A" value="On"/>
                <flagDependency flag="B" value="On"/>
            </dependencies>
        ''')
        self.assertTrue(skrim.fomod_dependencies_met(dependencies, {'A': 'On', 'B': 'On'}))
        self.assertFalse(skrim.fomod_dependencies_met(dependencies, {'A': 'On', 'B': 'Off'}))

    def test_or_operator_requires_one_flag(self):
        dependencies = fomod_xml('''
            <dependencies operator="Or">
                <flagDependency flag="A" value="On"/>
                <flagDependency flag="B" value="On"/>
            </dependencies>
        ''')
        self.assertTrue(skrim.fomod_dependencies_met(dependencies, {'A': 'Off', 'B': 'On'}))
        self.assertFalse(skrim.fomod_dependencies_met(dependencies, {'A': 'Off', 'B': 'Off'}))

    def test_missing_operator_defaults_to_and(self):
        dependencies = fomod_xml('''
            <dependencies>
                <flagDependency flag="A" value="On"/>
                <flagDependency flag="B" value="On"/>
            </dependencies>
        ''')
        self.assertFalse(skrim.fomod_dependencies_met(dependencies, {'A': 'On'}))

    def test_unset_flag_counts_as_off(self):
        dependencies = fomod_xml('''
            <dependencies operator="And">
                <flagDependency flag="NeverSet" value="Off"/>
            </dependencies>
        ''')
        self.assertTrue(skrim.fomod_dependencies_met(dependencies, {}))

    def test_unset_flag_does_not_count_as_on(self):
        dependencies = fomod_xml('''
            <dependencies operator="And">
                <flagDependency flag="NeverSet" value="On"/>
            </dependencies>
        ''')
        self.assertFalse(skrim.fomod_dependencies_met(dependencies, {}))

    def test_explicit_off_still_matches(self):
        dependencies = fomod_xml('''
            <dependencies operator="And">
                <flagDependency flag="A" value="Off"/>
            </dependencies>
        ''')
        self.assertTrue(skrim.fomod_dependencies_met(dependencies, {'A': 'Off'}))

    def test_file_dependency_active_matches_installed_file(self):
        dependencies = fomod_xml('''
            <dependencies operator="And">
                <fileDependency file="Some Mod.esp" state="Active"/>
            </dependencies>
        ''')
        self.assertTrue(skrim.fomod_dependencies_met(dependencies, {}, {'some mod.esp'}))
        self.assertFalse(skrim.fomod_dependencies_met(dependencies, {}, frozenset()))

    def test_file_dependency_missing_matches_uninstalled_file(self):
        dependencies = fomod_xml('''
            <dependencies operator="And">
                <fileDependency file="Some Mod.esp" state="Missing"/>
            </dependencies>
        ''')
        self.assertTrue(skrim.fomod_dependencies_met(dependencies, {}, frozenset()))
        self.assertFalse(skrim.fomod_dependencies_met(dependencies, {}, {'some mod.esp'}))

    def test_file_dependency_inactive_is_satisfied_by_presence(self):
        # skrim never tracks a disabled-but-installed state, so 'Inactive' just means "present"
        dependencies = fomod_xml('''
            <dependencies operator="Or">
                <fileDependency file="Some Mod.esp" state="Active"/>
                <fileDependency file="Some Mod.esp" state="Inactive"/>
            </dependencies>
        ''')
        self.assertTrue(skrim.fomod_dependencies_met(dependencies, {}, {'some mod.esp'}))
        self.assertFalse(skrim.fomod_dependencies_met(dependencies, {}, frozenset()))

    def test_mixed_flag_and_file_dependencies(self):
        dependencies = fomod_xml('''
            <dependencies operator="And">
                <flagDependency flag="A" value="On"/>
                <fileDependency file="Some Mod.esp" state="Active"/>
            </dependencies>
        ''')
        self.assertTrue(skrim.fomod_dependencies_met(dependencies, {'A': 'On'}, {'some mod.esp'}))
        self.assertFalse(skrim.fomod_dependencies_met(dependencies, {'A': 'On'}, frozenset()))

    def test_nested_dependencies(self):
        dependencies = fomod_xml('''
            <dependencies operator="And">
                <flagDependency flag="A" value="On"/>
                <dependencies operator="Or">
                    <flagDependency flag="B" value="On"/>
                    <flagDependency flag="C" value="On"/>
                </dependencies>
            </dependencies>
        ''')
        self.assertTrue(skrim.fomod_dependencies_met(dependencies, {'A': 'On', 'C': 'On'}))
        self.assertFalse(skrim.fomod_dependencies_met(dependencies, {'A': 'On'}))


class TestResolvePluginType(unittest.TestCase):

    def test_no_type_descriptor_defaults_to_optional(self):
        plugin = fomod_xml('<plugin name="P"/>')
        self.assertEqual(skrim.resolve_plugin_type(plugin, {}, frozenset()), 'Optional')

    def test_static_type(self):
        plugin = fomod_xml('<plugin name="P"><typeDescriptor><type name="Required"/></typeDescriptor></plugin>')
        self.assertEqual(skrim.resolve_plugin_type(plugin, {}, frozenset()), 'Required')

    def test_pattern_match_wins_over_default(self):
        plugin = fomod_xml('''
            <plugin name="P">
                <typeDescriptor>
                    <dependencyType>
                        <defaultType name="NotUsable"/>
                        <patterns>
                            <pattern>
                                <dependencies><fileDependency file="Base.esp" state="Active"/></dependencies>
                                <type name="Recommended"/>
                            </pattern>
                        </patterns>
                    </dependencyType>
                </typeDescriptor>
            </plugin>
        ''')
        self.assertEqual(skrim.resolve_plugin_type(plugin, {}, {'base.esp'}), 'Recommended')

    def test_falls_back_to_default_type_when_no_pattern_matches(self):
        plugin = fomod_xml('''
            <plugin name="P">
                <typeDescriptor>
                    <dependencyType>
                        <defaultType name="NotUsable"/>
                        <patterns>
                            <pattern>
                                <dependencies><fileDependency file="Base.esp" state="Active"/></dependencies>
                                <type name="Recommended"/>
                            </pattern>
                        </patterns>
                    </dependencyType>
                </typeDescriptor>
            </plugin>
        ''')
        self.assertEqual(skrim.resolve_plugin_type(plugin, {}, frozenset()), 'NotUsable')


class TestLoadFomodConfig(unittest.TestCase):

    def write_and_load(self, data):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = pathlib.Path(temp_dir)
            (temp_dir / 'fomod').mkdir()
            (temp_dir / 'fomod' / 'ModuleConfig.xml').write_bytes(data)
            paths = [pathlib.Path('fomod/ModuleConfig.xml')]
            return skrim.load_fomod_config(temp_dir, paths)

    def test_returns_none_when_no_fomod_present(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = skrim.load_fomod_config(pathlib.Path(temp_dir), [pathlib.Path('plugin.esp')])
        self.assertIsNone(result)

    def test_plain_utf8(self):
        config = self.write_and_load('<config><moduleName>Test</moduleName></config>'.encode('utf-8'))
        self.assertEqual(config.findtext('moduleName'), 'Test')

    def test_utf8_with_bom(self):
        config = self.write_and_load('<config><moduleName>Test</moduleName></config>'.encode('utf-8-sig'))
        self.assertEqual(config.findtext('moduleName'), 'Test')

    def test_utf16_le(self):
        config = self.write_and_load(b'\xff\xfe' + '<config><moduleName>Test</moduleName></config>'.encode('utf-16-le'))
        self.assertEqual(config.findtext('moduleName'), 'Test')

    def test_utf16_be(self):
        config = self.write_and_load(b'\xfe\xff' + '<config><moduleName>Test</moduleName></config>'.encode('utf-16-be'))
        self.assertEqual(config.findtext('moduleName'), 'Test')


class TestRecommendedPluginIndex(unittest.TestCase):

    def plugin_with_pattern(self, version, type_name):
        return fomod_xml(f'''
            <plugin name="P">
                <typeDescriptor>
                    <dependencyType>
                        <patterns>
                            <pattern>
                                <dependencies><gameDependency version="{version}"/></dependencies>
                                <type name="{type_name}"/>
                            </pattern>
                        </patterns>
                    </dependencyType>
                </typeDescriptor>
            </plugin>
        ''')

    def test_none_without_skyrim_version(self):
        plugins = [self.plugin_with_pattern('1.6.0.0', 'Recommended')]
        self.assertIsNone(skrim.recommended_plugin_index(plugins, None))

    def test_none_when_nothing_recommends_itself(self):
        plugins = [self.plugin_with_pattern('1.6.0.0', 'Optional')]
        self.assertIsNone(skrim.recommended_plugin_index(plugins, '1.6.1170.0'))

    def test_picks_recommended_plugin_under_detected_version(self):
        plugins = [self.plugin_with_pattern('1.6.1170.0', 'Recommended')]
        self.assertEqual(skrim.recommended_plugin_index(plugins, '1.7.104.0'), 1)

    def test_ignores_thresholds_above_detected_version(self):
        plugins = [self.plugin_with_pattern('1.9.0.0', 'Recommended')]
        self.assertIsNone(skrim.recommended_plugin_index(plugins, '1.7.104.0'))

    def test_picks_highest_applicable_threshold(self):
        plugins = [
            self.plugin_with_pattern('1.5.0.0', 'Recommended'),
            self.plugin_with_pattern('1.6.1170.0', 'Recommended'),
        ]
        self.assertEqual(skrim.recommended_plugin_index(plugins, '1.7.104.0'), 2)


class TestCalculateFomodChoices(unittest.TestCase):

    def test_select_exactly_one_prompts_and_returns_the_picked_name(self):
        config = fomod_xml('''
            <config><installSteps><installStep name="Step"><optionalFileGroups>
                <group name="Group" type="SelectExactlyOne">
                    <plugins>
                        <plugin name="A"/>
                        <plugin name="B"/>
                    </plugins>
                </group>
            </optionalFileGroups></installStep></installSteps></config>
        ''')
        with unittest.mock.patch('builtins.input', return_value='2'):
            choices = skrim.calculate_fomod_choices(config, None)
        self.assertEqual(choices, {'Group': 'B'})

    def test_select_exactly_one_reuses_remembered_choice_without_prompting(self):
        config = fomod_xml('''
            <config><installSteps><installStep name="Step"><optionalFileGroups>
                <group name="Group" type="SelectExactlyOne">
                    <plugins>
                        <plugin name="A"/>
                        <plugin name="B"/>
                    </plugins>
                </group>
            </optionalFileGroups></installStep></installSteps></config>
        ''')
        with unittest.mock.patch('builtins.input') as mock_input:
            choices = skrim.calculate_fomod_choices(config, {'Group': 'B'})
        mock_input.assert_not_called()
        self.assertEqual(choices, {'Group': 'B'})

    def test_select_any_accepts_comma_separated_picks(self):
        config = fomod_xml('''
            <config><installSteps><installStep name="Step"><optionalFileGroups>
                <group name="Group" type="SelectAny">
                    <plugins>
                        <plugin name="A"/>
                        <plugin name="B"/>
                        <plugin name="C"/>
                    </plugins>
                </group>
            </optionalFileGroups></installStep></installSteps></config>
        ''')
        with unittest.mock.patch('builtins.input', return_value='1,3'):
            choices = skrim.calculate_fomod_choices(config, None)
        self.assertEqual(choices, {'Group': ['A', 'C']})

    def test_select_any_blank_means_none_picked(self):
        config = fomod_xml('''
            <config><installSteps><installStep name="Step"><optionalFileGroups>
                <group name="Group" type="SelectAny">
                    <plugins><plugin name="A"/></plugins>
                </group>
            </optionalFileGroups></installStep></installSteps></config>
        ''')
        with unittest.mock.patch('builtins.input', return_value=''):
            choices = skrim.calculate_fomod_choices(config, None)
        self.assertEqual(choices, {'Group': []})

    def test_select_at_most_one_rejects_multiple_picks(self):
        config = fomod_xml('''
            <config><installSteps><installStep name="Step"><optionalFileGroups>
                <group name="Group" type="SelectAtMostOne">
                    <plugins>
                        <plugin name="A"/>
                        <plugin name="B"/>
                    </plugins>
                </group>
            </optionalFileGroups></installStep></installSteps></config>
        ''')
        with unittest.mock.patch('builtins.input', side_effect=['1,2', '1']):
            choices = skrim.calculate_fomod_choices(config, None)
        self.assertEqual(choices, {'Group': ['A']})

    def test_select_all_does_not_prompt(self):
        config = fomod_xml('''
            <config><installSteps><installStep name="Step"><optionalFileGroups>
                <group name="Group" type="SelectAll">
                    <plugins>
                        <plugin name="A"/>
                        <plugin name="B"/>
                    </plugins>
                </group>
            </optionalFileGroups></installStep></installSteps></config>
        ''')
        with unittest.mock.patch('builtins.input') as mock_input:
            choices = skrim.calculate_fomod_choices(config, None)
        mock_input.assert_not_called()
        self.assertEqual(choices, {'Group': ['A', 'B']})

    def test_unsupported_group_type_raises(self):
        config = fomod_xml('''
            <config><installSteps><installStep name="Step"><optionalFileGroups>
                <group name="Group" type="SelectAtLeastOne">
                    <plugins><plugin name="A"/></plugins>
                </group>
            </optionalFileGroups></installStep></installSteps></config>
        ''')
        with self.assertRaises(NotImplementedError):
            skrim.calculate_fomod_choices(config, None)

    def test_hidden_step_is_skipped_entirely(self):
        config = fomod_xml('''
            <config><installSteps>
                <installStep name="Gate"><optionalFileGroups>
                    <group name="Gate Group" type="SelectAny">
                        <plugins><plugin name="Enable"/></plugins>
                    </group>
                </optionalFileGroups></installStep>
                <installStep name="Hidden">
                    <visible>
                        <dependencies operator="And">
                            <flagDependency flag="ShowNext" value="On"/>
                        </dependencies>
                    </visible>
                    <optionalFileGroups>
                        <group name="Hidden Group" type="SelectExactlyOne">
                            <plugins><plugin name="X"/></plugins>
                        </group>
                    </optionalFileGroups>
                </installStep>
            </installSteps></config>
        ''')
        with unittest.mock.patch('builtins.input', return_value=''):
            choices = skrim.calculate_fomod_choices(config, None)
        self.assertNotIn('Hidden Group', choices)

    def test_select_any_hides_not_usable_plugins_and_defaults_recommended(self):
        config = fomod_xml('''
            <config><installSteps><installStep name="Step"><optionalFileGroups>
                <group name="Group" type="SelectAny">
                    <plugins>
                        <plugin name="Installed Patch">
                            <typeDescriptor><dependencyType>
                                <defaultType name="NotUsable"/>
                                <patterns><pattern>
                                    <dependencies><fileDependency file="Installed.esp" state="Active"/></dependencies>
                                    <type name="Recommended"/>
                                </pattern></patterns>
                            </dependencyType></typeDescriptor>
                        </plugin>
                        <plugin name="Uninstalled Patch">
                            <typeDescriptor><dependencyType>
                                <defaultType name="NotUsable"/>
                                <patterns><pattern>
                                    <dependencies><fileDependency file="NotInstalled.esp" state="Active"/></dependencies>
                                    <type name="Recommended"/>
                                </pattern></patterns>
                            </dependencyType></typeDescriptor>
                        </plugin>
                    </plugins>
                </group>
            </optionalFileGroups></installStep></installSteps></config>
        ''')
        with tempfile.TemporaryDirectory() as game_dir:
            (pathlib.Path(game_dir) / 'Data').mkdir()
            (pathlib.Path(game_dir) / 'Data' / 'Installed.esp').touch()

            with unittest.mock.patch('builtins.input', return_value='') as mock_input:
                choices = skrim.calculate_fomod_choices(config, None, game_dir=game_dir)

        mock_input.assert_called_once()
        self.assertEqual(choices, {'Group': ['Installed Patch']})

    def test_select_any_skips_prompt_entirely_when_nothing_is_usable(self):
        config = fomod_xml('''
            <config><installSteps><installStep name="Step"><optionalFileGroups>
                <group name="Group" type="SelectAny">
                    <plugins>
                        <plugin name="Uninstalled Patch">
                            <typeDescriptor><dependencyType>
                                <defaultType name="NotUsable"/>
                                <patterns><pattern>
                                    <dependencies><fileDependency file="NotInstalled.esp" state="Active"/></dependencies>
                                    <type name="Recommended"/>
                                </pattern></patterns>
                            </dependencyType></typeDescriptor>
                        </plugin>
                    </plugins>
                </group>
            </optionalFileGroups></installStep></installSteps></config>
        ''')
        with tempfile.TemporaryDirectory() as game_dir:
            (pathlib.Path(game_dir) / 'Data').mkdir()

            with unittest.mock.patch('builtins.input') as mock_input:
                choices = skrim.calculate_fomod_choices(config, None, game_dir=game_dir)

        mock_input.assert_not_called()
        self.assertEqual(choices, {'Group': []})

    def test_select_exactly_one_defaults_to_the_single_recommended_plugin(self):
        config = fomod_xml('''
            <config><installSteps><installStep name="Step"><optionalFileGroups>
                <group name="Group" type="SelectExactlyOne">
                    <plugins>
                        <plugin name="A">
                            <typeDescriptor><dependencyType>
                                <defaultType name="Optional"/>
                                <patterns><pattern>
                                    <dependencies><fileDependency file="Installed.esp" state="Active"/></dependencies>
                                    <type name="Recommended"/>
                                </pattern></patterns>
                            </dependencyType></typeDescriptor>
                        </plugin>
                        <plugin name="B"/>
                    </plugins>
                </group>
            </optionalFileGroups></installStep></installSteps></config>
        ''')
        with tempfile.TemporaryDirectory() as game_dir:
            (pathlib.Path(game_dir) / 'Data').mkdir()
            (pathlib.Path(game_dir) / 'Data' / 'Installed.esp').touch()

            with unittest.mock.patch('builtins.input', return_value=''):
                choices = skrim.calculate_fomod_choices(config, None, game_dir=game_dir)

        self.assertEqual(choices, {'Group': 'A'})

    def test_visible_step_is_shown_once_its_flag_is_set(self):
        config = fomod_xml('''
            <config><installSteps>
                <installStep name="Gate"><optionalFileGroups>
                    <group name="Gate Group" type="SelectAny">
                        <plugins>
                            <plugin name="Enable">
                                <conditionFlags><flag name="ShowNext">On</flag></conditionFlags>
                            </plugin>
                        </plugins>
                    </group>
                </optionalFileGroups></installStep>
                <installStep name="Revealed">
                    <visible>
                        <dependencies operator="And">
                            <flagDependency flag="ShowNext" value="On"/>
                        </dependencies>
                    </visible>
                    <optionalFileGroups>
                        <group name="Revealed Group" type="SelectExactlyOne">
                            <plugins><plugin name="X"/></plugins>
                        </group>
                    </optionalFileGroups>
                </installStep>
            </installSteps></config>
        ''')
        with unittest.mock.patch('builtins.input', side_effect=['1', '1']):
            choices = skrim.calculate_fomod_choices(config, None)
        self.assertEqual(choices, {'Gate Group': ['Enable'], 'Revealed Group': 'X'})


class TestCalculateFomodTargets(unittest.TestCase):

    def test_required_folder_mirrors_recursively(self):
        config = fomod_xml('''
            <config><requiredInstallFiles>
                <folder source="Core" destination=""/>
            </requiredInstallFiles></config>
        ''')
        paths = [pathlib.Path('Core/plugin.esp'), pathlib.Path('Core/sub/mesh.nif')]
        targets = skrim.calculate_fomod_targets(config, {}, paths)
        self.assertCountEqual(targets, [
            (pathlib.Path('Core/plugin.esp'), pathlib.Path('Data/plugin.esp')),
            (pathlib.Path('Core/sub/mesh.nif'), pathlib.Path('Data/sub/mesh.nif')),
        ])

    def test_required_bare_file_maps_to_its_destination(self):
        config = fomod_xml('''
            <config><requiredInstallFiles>
                <file source="Core\\Mod.bsa" destination="Mod.bsa"/>
            </requiredInstallFiles></config>
        ''')
        paths = [pathlib.Path('Core/Mod.bsa')]
        targets = skrim.calculate_fomod_targets(config, {}, paths)
        self.assertEqual(targets, [(pathlib.Path('Core/Mod.bsa'), pathlib.Path('Data/Mod.bsa'))])

    def test_only_chosen_plugin_files_are_installed(self):
        config = fomod_xml('''
            <config><installSteps><installStep name="Step"><optionalFileGroups>
                <group name="Group" type="SelectExactlyOne">
                    <plugins>
                        <plugin name="A"><files><file source="a.esp" destination="a.esp"/></files></plugin>
                        <plugin name="B"><files><file source="b.esp" destination="b.esp"/></files></plugin>
                    </plugins>
                </group>
            </optionalFileGroups></installStep></installSteps></config>
        ''')
        paths = [pathlib.Path('a.esp'), pathlib.Path('b.esp')]
        targets = skrim.calculate_fomod_targets(config, {'Group': 'A'}, paths)
        self.assertEqual(targets, [(pathlib.Path('a.esp'), pathlib.Path('Data/a.esp'))])

    def test_conditional_file_install_fires_when_flags_match(self):
        config = fomod_xml('''
            <config><installSteps><installStep name="Step"><optionalFileGroups>
                <group name="Group" type="SelectAny">
                    <plugins>
                        <plugin name="Enable">
                            <conditionFlags><flag name="Ready">On</flag></conditionFlags>
                        </plugin>
                    </plugins>
                </group>
            </optionalFileGroups></installStep></installSteps>
            <conditionalFileInstalls><patterns><pattern>
                <dependencies operator="And"><flagDependency flag="Ready" value="On"/></dependencies>
                <files><file source="patch.esp" destination="patch.esp"/></files>
            </pattern></patterns></conditionalFileInstalls></config>
        ''')
        paths = [pathlib.Path('patch.esp')]
        targets = skrim.calculate_fomod_targets(config, {'Group': ['Enable']}, paths)
        self.assertEqual(targets, [(pathlib.Path('patch.esp'), pathlib.Path('Data/patch.esp'))])

    def test_conditional_file_install_skipped_when_flags_dont_match(self):
        config = fomod_xml('''
            <config><installSteps><installStep name="Step"><optionalFileGroups>
                <group name="Group" type="SelectAny">
                    <plugins>
                        <plugin name="Enable">
                            <conditionFlags><flag name="Ready">On</flag></conditionFlags>
                        </plugin>
                    </plugins>
                </group>
            </optionalFileGroups></installStep></installSteps>
            <conditionalFileInstalls><patterns><pattern>
                <dependencies operator="And"><flagDependency flag="Ready" value="On"/></dependencies>
                <files><file source="patch.esp" destination="patch.esp"/></files>
            </pattern></patterns></conditionalFileInstalls></config>
        ''')
        paths = [pathlib.Path('patch.esp')]
        targets = skrim.calculate_fomod_targets(config, {'Group': []}, paths)
        self.assertEqual(targets, [])

    def test_hidden_step_groups_are_not_looked_up_in_choices(self):
        config = fomod_xml('''
            <config><installSteps>
                <installStep name="Gate"><optionalFileGroups>
                    <group name="Gate Group" type="SelectAny">
                        <plugins><plugin name="Enable"/></plugins>
                    </group>
                </optionalFileGroups></installStep>
                <installStep name="Hidden">
                    <visible>
                        <dependencies operator="And">
                            <flagDependency flag="ShowNext" value="On"/>
                        </dependencies>
                    </visible>
                    <optionalFileGroups>
                        <group name="Hidden Group" type="SelectExactlyOne">
                            <plugins><plugin name="X"><files><file source="x.esp" destination="x.esp"/></files></plugin></plugins>
                        </group>
                    </optionalFileGroups>
                </installStep>
            </installSteps></config>
        ''')
        choices = {'Gate Group': []}
        targets = skrim.calculate_fomod_targets(config, choices, [pathlib.Path('x.esp')])
        self.assertEqual(targets, [])


if __name__ == '__main__':
    unittest.main()
