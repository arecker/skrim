package main

/*
#cgo pkg-config: libarchive
#include <archive.h>
#include <archive_entry.h>
#include <stdlib.h>
*/
import "C"

import (
	"archive/zip"
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"encoding/xml"
	"flag"
	"fmt"
	"io"
	"os"
	"path"
	"path/filepath"
	"regexp"
	"runtime"
	"strconv"
	"strings"
	"unicode/utf16"
	"unsafe"
)

var verboseLogging bool
var stdinReader = bufio.NewReader(os.Stdin)

func main() {
	args := parseArgs()
	verboseLogging = args.verbose

	wd, _ := os.Getwd()
	logDebug("starting skrim (go_version = %s, pwd = %s, args = %+v)", runtime.Version(), wd, args)

	cfg, mods, err := loadConfig(args.config)
	if err != nil {
		logError("%v", err)
		os.Exit(1)
	}

	logInfo("loaded %d mod(s) from %s", len(mods), args.config)

	if args.validate {
		logInfo("requirements OK for %d mod(s)", len(mods))
		return
	}

	lockFile := lockFilePath(args.config)

	installs, err := loadInstallations(lockFile)
	if err != nil {
		logError("%v", err)
		os.Exit(1)
	}
	logInfo("loaded %d installed mod(s) from %s", len(installs), lockFile)

	oldFomodChoices := map[string]map[string]any{}
	if !args.again {
		for _, inst := range installs {
			if inst.FomodChoices != nil {
				oldFomodChoices[inst.ModName] = inst.FomodChoices
			}
		}
	}

	skyrimVersion := sniffOutSkyrimVersion(cfg.gameDir)
	if skyrimVersion != nil {
		logInfo("sniffed out skyrim version: %s", *skyrimVersion)
	} else {
		logInfo("sniffed out skyrim version: none")
	}

	if args.pave {
		if err := toggleIniPatch(cfg.iniFile, true); err != nil {
			logError("%v", err)
			os.Exit(1)
		}
		if err := togglePluginsFile(installs, cfg.pluginsFile, true); err != nil {
			logError("%v", err)
			os.Exit(1)
		}
		paveInstallations(installs)
		return
	}

	installsByName := map[string]installation{}
	for _, inst := range installs {
		installsByName[inst.ModName] = inst
	}
	configModNames := map[string]bool{}
	for _, m := range mods {
		configModNames[m.name] = true
	}

	var dropped []installation
	for _, inst := range installs {
		if !configModNames[inst.ModName] {
			dropped = append(dropped, inst)
		}
	}
	if len(dropped) > 0 {
		paveInstallations(dropped)
	}

	var newInstalls []installation
	changed := map[string]bool{}

	writePartialAndExit := func(err error) {
		if werr := writeInstallations(newInstalls, lockFile); werr == nil {
			logInfo("wrote partial %s", lockFile)
		}
		logError("%v", err)
		os.Exit(1)
	}

	for i, m := range mods {
		oldInstall, hadOld := installsByName[m.name]
		packageHash, err := hashPackage(filepath.Join(cfg.downloadsDir, m.filename))
		if err != nil {
			writePartialAndExit(err)
		}

		requiresChanged := false
		for _, req := range m.requires {
			if changed[req] {
				requiresChanged = true
				break
			}
		}

		if hadOld && oldInstall.PackageHash == packageHash {
			allPresent := true
			for _, target := range oldInstall.Targets {
				if info, err := os.Stat(target); err != nil || info.IsDir() {
					allPresent = false
					break
				}
			}

			if !requiresChanged && allPresent {
				logInfo("skipping [%s] (%d/%d), unchanged and all targets present", m.name, i+1, len(mods))
				newInstalls = append(newInstalls, oldInstall)
				continue
			} else if requiresChanged {
				logInfo("reinstalling [%s] (%d/%d), a required mod was updated", m.name, i+1, len(mods))
			} else {
				logInfo("reinstalling [%s] (%d/%d), unchanged but missing targets", m.name, i+1, len(mods))
			}
		} else {
			logInfo("installing [%s] (%d/%d)", m.name, i+1, len(mods))
			if hadOld {
				paveInstallations([]installation{oldInstall})
				delete(oldFomodChoices, m.name)
			}
		}

		install, err := installMod(m, cfg.downloadsDir, cfg.gameDir, oldFomodChoices[m.name], skyrimVersion)
		if err != nil {
			writePartialAndExit(err)
		}
		newInstalls = append(newInstalls, install)
		changed[m.name] = true
		logInfo("copied %d file(s) to game directory", len(install.Targets))
	}

	if err := toggleIniPatch(cfg.iniFile, false); err != nil {
		logError("%v", err)
		os.Exit(1)
	}
	logInfo("applied patch to %s", cfg.iniFile)

	if err := togglePluginsFile(newInstalls, cfg.pluginsFile, false); err != nil {
		logError("%v", err)
		os.Exit(1)
	}

	if err := writeInstallations(newInstalls, lockFile); err != nil {
		logError("%v", err)
		os.Exit(1)
	}
	logInfo("wrote %s", lockFile)
}

type cliArgs struct {
	config   string
	pave     bool
	validate bool
	again    bool
	verbose  bool
}

func parseArgs() cliArgs {
	fs := flag.NewFlagSet("skrim", flag.ExitOnError)

	var configPath string
	fs.StringVar(&configPath, "config", "", "path to the config file (required)")
	fs.StringVar(&configPath, "c", "", "path to the config file (required)")

	var pave, validate, again, verbose bool
	fs.BoolVar(&pave, "pave", false, "return skyrim back to its vanilla state")
	fs.BoolVar(&validate, "validate", false, "check mod requirements and exit")
	fs.BoolVar(&again, "again", false, "prompt interactive installers again")
	fs.BoolVar(&verbose, "verbose", false, "show debug logs")
	fs.BoolVar(&verbose, "v", false, "show debug logs")

	fs.Usage = func() {
		fmt.Fprintln(os.Stderr, "manage your skyrim mods like an adult")
		fmt.Fprintln(os.Stderr)
		fmt.Fprintln(os.Stderr, "Usage of skrim:")
		fs.PrintDefaults()
	}

	fs.Parse(os.Args[1:])

	if configPath == "" {
		fmt.Fprintln(os.Stderr, "skrim: error: -c/--config is required")
		fs.Usage()
		os.Exit(2)
	}

	return cliArgs{config: configPath, pave: pave, validate: validate, again: again, verbose: verbose}
}

func logDebug(format string, args ...any) {
	if verboseLogging {
		fmt.Fprintf(os.Stderr, "DEBUG: "+format+"\n", args...)
	}
}

func logInfo(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "INFO: "+format+"\n", args...)
}

func logWarn(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "WARNING: "+format+"\n", args...)
}

func logError(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "ERROR: "+format+"\n", args...)
}

type iniSection struct {
	keyOrder []string
	values   map[string]string
}

func (s *iniSection) get(key string) (string, bool) {
	v, ok := s.values[key]
	return v, ok
}

func (s *iniSection) set(key, value string) {
	if _, ok := s.values[key]; !ok {
		s.keyOrder = append(s.keyOrder, key)
	}
	s.values[key] = value
}

func (s *iniSection) remove(key string) {
	if _, ok := s.values[key]; ok {
		delete(s.values, key)
		for i, k := range s.keyOrder {
			if k == key {
				s.keyOrder = append(s.keyOrder[:i], s.keyOrder[i+1:]...)
				break
			}
		}
	}
}

type iniFile struct {
	sectionOrder []string
	sections     map[string]*iniSection
}

func newIniFile() *iniFile {
	return &iniFile{sections: map[string]*iniSection{}}
}

func (f *iniFile) section(name string) *iniSection {
	return f.sections[name]
}

func (f *iniFile) hasSection(name string) bool {
	_, ok := f.sections[name]
	return ok
}

func (f *iniFile) ensureSection(name string) *iniSection {
	s, ok := f.sections[name]
	if !ok {
		s = &iniSection{values: map[string]string{}}
		f.sections[name] = s
		f.sectionOrder = append(f.sectionOrder, name)
	}
	return s
}

func parseIni(path string) (*iniFile, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	f := newIniFile()
	var current *iniSection

	for _, rawLine := range strings.Split(string(data), "\n") {
		line := strings.TrimRight(rawLine, "\r")
		trimmed := strings.TrimSpace(line)

		if trimmed == "" || strings.HasPrefix(trimmed, "#") || strings.HasPrefix(trimmed, ";") {
			continue
		}

		if strings.HasPrefix(trimmed, "[") && strings.HasSuffix(trimmed, "]") {
			name := strings.TrimSpace(trimmed[1 : len(trimmed)-1])
			current = f.ensureSection(name)
			continue
		}

		if current == nil {
			continue
		}

		key, value, found := strings.Cut(trimmed, "=")
		if !found {
			continue
		}

		current.set(strings.TrimSpace(key), strings.TrimSpace(value))
	}

	return f, nil
}

func (f *iniFile) write(path string) error {
	var b strings.Builder

	for i, name := range f.sectionOrder {
		if i > 0 {
			b.WriteString("\n")
		}
		b.WriteString("[" + name + "]\n")
		section := f.sections[name]
		for _, key := range section.keyOrder {
			b.WriteString(key + " = " + section.values[key] + "\n")
		}
	}

	return os.WriteFile(path, []byte(b.String()), 0644)
}

type config struct {
	downloadsDir string
	gameDir      string
	pluginsFile  string
	iniFile      string
}

type mod struct {
	name     string
	filename string
	requires []string
}

type configProblem struct {
	msg string
}

func (e *configProblem) Error() string { return e.msg }

func configProblemf(format string, args ...any) error {
	return &configProblem{msg: fmt.Sprintf(format, args...)}
}

func expandUser(p string) string {
	if p == "~" {
		home, _ := os.UserHomeDir()
		return home
	}
	if strings.HasPrefix(p, "~/") {
		home, _ := os.UserHomeDir()
		return filepath.Join(home, p[2:])
	}
	return p
}

func mustAbs(p string) string {
	abs, err := filepath.Abs(p)
	if err != nil {
		return p
	}
	return abs
}

func buildConfig(s *iniSection) (config, error) {
	get := func(key string) (string, error) {
		v, ok := s.get(key)
		if !ok {
			return "", fmt.Errorf("missing required field: %s", key)
		}
		return v, nil
	}

	downloadsDir, err := get("downloads_dir")
	if err != nil {
		return config{}, err
	}
	gameDir, err := get("game_dir")
	if err != nil {
		return config{}, err
	}
	pluginsFile, err := get("plugins_file")
	if err != nil {
		return config{}, err
	}
	iniFile, err := get("ini_file")
	if err != nil {
		return config{}, err
	}

	return config{downloadsDir: downloadsDir, gameDir: gameDir, pluginsFile: pluginsFile, iniFile: iniFile}, nil
}

func loadConfig(configPath string) (config, []mod, error) {
	if info, err := os.Stat(configPath); err != nil || info.IsDir() {
		return config{}, nil, configProblemf("config file does not exist: %s", configPath)
	}

	ini, err := parseIni(configPath)
	if err != nil {
		return config{}, nil, configProblemf("failed to parse config file %s: %v", configPath, err)
	}

	skrimSection := ini.section("skrim")
	if skrimSection == nil {
		return config{}, nil, configProblemf("[skrim] section missing from %s", configPath)
	}

	cfg, err := buildConfig(skrimSection)
	if err != nil {
		return config{}, nil, configProblemf("[skrim] is misconfigured! %v", err)
	}
	cfg.downloadsDir = expandUser(cfg.downloadsDir)
	cfg.gameDir = mustAbs(expandUser(cfg.gameDir))
	cfg.pluginsFile = mustAbs(expandUser(cfg.pluginsFile))
	cfg.iniFile = mustAbs(expandUser(cfg.iniFile))

	var mods []mod
	for _, name := range ini.sectionOrder {
		if name == "skrim" {
			continue
		}
		section := ini.sections[name]

		filename, _ := section.get("filename")
		requiresRaw, _ := section.get("requires")

		var requires []string
		for _, part := range strings.Split(requiresRaw, ",") {
			part = strings.TrimSpace(part)
			if part != "" {
				requires = append(requires, part)
			}
		}

		if filename == "" {
			return config{}, nil, configProblemf("[%s] is misconfigured! missing filename", name)
		}

		m := mod{name: name, filename: filename, requires: requires}

		modPath := filepath.Join(cfg.downloadsDir, m.filename)
		if info, err := os.Stat(modPath); err != nil || info.IsDir() {
			return config{}, nil, configProblemf("[%s] file does not exist: %s", name, modPath)
		}

		mods = append(mods, m)
	}

	if err := validateRequirements(mods); err != nil {
		return config{}, nil, err
	}

	return cfg, mods, nil
}

func validateRequirements(mods []mod) error {
	index := map[string]int{}
	for i, m := range mods {
		index[m.name] = i
	}
	for i, m := range mods {
		for _, req := range m.requires {
			reqIndex, ok := index[req]
			if !ok {
				return configProblemf("[%s] requires [%s], which is not in config", m.name, req)
			}
			if reqIndex > i {
				return configProblemf("[%s] requires [%s], which is listed after it in config", m.name, req)
			}
		}
	}
	return nil
}

func lockFilePath(configPath string) string {
	dir := filepath.Dir(configPath)
	base := filepath.Base(configPath)
	ext := filepath.Ext(base)
	stem := strings.TrimSuffix(base, ext)
	return filepath.Join(dir, stem+".lock.json")
}

func toggleIniPatch(iniPath string, off bool) error {
	f, err := parseIni(iniPath)
	if err != nil {
		return err
	}

	if off {
		if f.hasSection("Archive") {
			logInfo("removing ini patch from %s", iniPath)
			f.section("Archive").remove("bInvalidateOlderFiles")
			f.section("Archive").remove("sResourceDataDirsFinal")
		}
		if f.hasSection("Papyrus") {
			f.section("Papyrus").remove("bEnableLogging")
			f.section("Papyrus").remove("bEnableTrace")
		}
	} else {
		logInfo("adding ini patch to %s", iniPath)

		if !f.hasSection("Archive") {
			return fmt.Errorf("[Archive] section missing from %s", iniPath)
		}
		f.section("Archive").set("bInvalidateOlderFiles", "1")
		f.section("Archive").set("sResourceDataDirsFinal", "")

		if !f.hasSection("Papyrus") {
			return fmt.Errorf("[Papyrus] section missing from %s", iniPath)
		}
		f.section("Papyrus").set("bEnableLogging", "1")
		f.section("Papyrus").set("bEnableTrace", "1")
	}

	return f.write(iniPath)
}

func splitLines(text string) []string {
	if text == "" {
		return nil
	}
	text = strings.ReplaceAll(text, "\r\n", "\n")
	lines := strings.Split(text, "\n")
	if len(lines) > 0 && lines[len(lines)-1] == "" {
		lines = lines[:len(lines)-1]
	}
	return lines
}

func togglePluginsFile(installations []installation, pluginsPath string, off bool) error {
	var pluginNames []string
	for _, inst := range installations {
		for _, target := range inst.Targets {
			ext := filepath.Ext(target)
			if ext == ".esp" || ext == ".esl" || ext == ".esm" {
				pluginNames = append(pluginNames, filepath.Base(target))
			}
		}
	}

	contains := func(name string) bool {
		for _, n := range pluginNames {
			if n == name {
				return true
			}
		}
		return false
	}

	data, err := os.ReadFile(pluginsPath)
	if err != nil {
		return err
	}

	var lines []string
	for _, line := range splitLines(string(data)) {
		if contains(strings.TrimLeft(line, "*")) {
			continue
		}
		lines = append(lines, line)
	}

	if off {
		logInfo("removing plugins file patch from %s", pluginsPath)
	} else {
		logInfo("adding plugins file patch to %s", pluginsPath)
		for _, name := range pluginNames {
			lines = append(lines, "*"+name)
		}
	}

	return os.WriteFile(pluginsPath, []byte(strings.Join(lines, "\n")+"\n"), 0644)
}

var versionRegex = regexp.MustCompile(`\d+\.\d+\.\d+\.\d+`)

func parseVersionParts(v string) []int {
	fields := strings.Split(v, ".")
	parts := make([]int, len(fields))
	for i, f := range fields {
		n, _ := strconv.Atoi(f)
		parts[i] = n
	}
	return parts
}

func compareVersions(a, b []int) int {
	n := len(a)
	if len(b) < n {
		n = len(b)
	}
	for i := 0; i < n; i++ {
		if a[i] != b[i] {
			return a[i] - b[i]
		}
	}
	return len(a) - len(b)
}

func sniffOutSkyrimVersion(gameDir string) *string {
	exePath := filepath.Join(gameDir, "SkyrimSE.exe")
	data, err := os.ReadFile(exePath)
	if err != nil {
		return nil
	}

	if len(data)%2 != 0 {
		data = data[:len(data)-1]
	}

	u16 := make([]uint16, len(data)/2)
	for i := range u16 {
		u16[i] = uint16(data[2*i]) | uint16(data[2*i+1])<<8
	}
	text := string(utf16.Decode(u16))

	matches := versionRegex.FindAllString(text, -1)
	if len(matches) == 0 {
		return nil
	}

	best := matches[0]
	bestParts := parseVersionParts(best)
	for _, m := range matches[1:] {
		parts := parseVersionParts(m)
		if compareVersions(parts, bestParts) > 0 {
			best = m
			bestParts = parts
		}
	}

	return &best
}

type installation struct {
	ModName      string         `json:"mod_name"`
	Targets      []string       `json:"targets"`
	FomodChoices map[string]any `json:"fomod_choices"`
	PackageHash  string         `json:"package_hash"`
}

func loadInstallations(lockfilePath string) ([]installation, error) {
	data, err := os.ReadFile(lockfilePath)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}

	var installs []installation
	if err := json.Unmarshal(data, &installs); err != nil {
		return nil, err
	}
	return installs, nil
}

func writeInstallations(installs []installation, lockfilePath string) error {
	if installs == nil {
		installs = []installation{}
	}
	data, err := json.MarshalIndent(installs, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(lockfilePath, data, 0644)
}

func paveInstallations(installations []installation) {
	for _, inst := range installations {
		logInfo("paving [%s]", inst.ModName)
		for _, target := range inst.Targets {
			logDebug("deleting [%s] target %s", inst.ModName, target)
			if err := os.Remove(target); err != nil && !os.IsNotExist(err) {
				logWarn("failed to delete [%s] target %s: %v", inst.ModName, target, err)
			}
		}
	}
}

func hashPackage(packagePath string) (string, error) {
	f, err := os.Open(packagePath)
	if err != nil {
		return "", err
	}
	defer f.Close()

	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

func cleanupCopied(copied []string) {
	for _, target := range copied {
		if info, err := os.Stat(target); err == nil && !info.IsDir() {
			os.Remove(target)
		}
	}
}

func installMod(m mod, downloadsDir, gameDir string, oldFomodChoices map[string]any, skyrimVersion *string) (installation, error) {
	packagePath := filepath.Join(downloadsDir, m.filename)
	packageHash, err := hashPackage(packagePath)
	if err != nil {
		return installation{}, err
	}

	logInfo("unpacking [%s]", m.name)

	tempDir, paths, cleanup, err := packageUnzippedInTempDir(packagePath)
	if err != nil {
		return installation{}, err
	}
	defer cleanup()

	var fomodChoices map[string]any
	var targets [][2]string

	fomodConfig, err := loadFomodConfig(tempDir, paths)
	if err != nil {
		return installation{}, err
	}

	if fomodConfig != nil {
		fomodChoices = calculateFomodChoices(fomodConfig, oldFomodChoices, skyrimVersion, gameDir)
		targets = calculateFomodTargets(fomodConfig, fomodChoices, paths, gameDir)
	} else {
		targets = calculateHeuristicTargets(paths)
	}

	if len(targets) == 0 {
		return installation{}, fmt.Errorf("[%s] did not match any targets and that is a problem!", m.name)
	}

	var copied []string
	for _, t := range targets {
		src := filepath.Join(tempDir, filepath.FromSlash(t[0]))
		dst, err := filepath.Abs(filepath.Join(gameDir, filepath.FromSlash(t[1])))
		if err != nil {
			cleanupCopied(copied)
			return installation{}, err
		}
		logDebug("copying [%s] target %s -> %s", m.name, src, dst)

		if err := os.MkdirAll(filepath.Dir(dst), 0755); err != nil {
			cleanupCopied(copied)
			return installation{}, err
		}

		data, err := os.ReadFile(src)
		if err != nil {
			cleanupCopied(copied)
			return installation{}, err
		}
		if err := os.WriteFile(dst, data, 0644); err != nil {
			cleanupCopied(copied)
			return installation{}, err
		}
		copied = append(copied, dst)
	}

	return installation{ModName: m.name, Targets: copied, FomodChoices: fomodChoices, PackageHash: packageHash}, nil
}

func calculateHeuristicTargets(paths []string) [][2]string {
	var targets [][2]string

	topLevel := func(p string) bool {
		return !strings.Contains(p, "/")
	}

	for _, p := range paths {
		if topLevel(p) && (strings.HasSuffix(p, ".exe") || strings.HasSuffix(p, ".dll")) {
			targets = append(targets, [2]string{p, p})
		}
	}

	for _, p := range paths {
		parts := strings.Split(p, "/")
		if strings.ToLower(parts[0]) == "data" {
			dst := strings.Join(append([]string{"Data"}, parts[1:]...), "/")
			targets = append(targets, [2]string{p, dst})
		}
	}

	for _, p := range paths {
		parts := strings.Split(p, "/")
		if strings.ToLower(parts[0]) == "skse" {
			targets = append(targets, [2]string{p, "Data/" + p})
		}
	}

	for _, ext := range []string{".esp", ".esl", ".esm", ".bsa", ".bsl", ".ini"} {
		for _, p := range paths {
			if topLevel(p) && strings.HasSuffix(p, ext) {
				targets = append(targets, [2]string{p, "Data/" + p})
			}
		}
	}

	accountedFor := map[string]bool{"data": true, "skse": true}
	for _, p := range paths {
		parts := strings.Split(p, "/")
		if len(parts) > 1 && !accountedFor[strings.ToLower(parts[0])] {
			targets = append(targets, [2]string{p, "Data/" + p})
		}
	}

	return targets
}

func safeJoin(base, rel string) (string, error) {
	if path.IsAbs(rel) {
		return "", fmt.Errorf("unsafe path in archive: %s", rel)
	}
	for _, part := range strings.Split(rel, "/") {
		if part == ".." {
			return "", fmt.Errorf("unsafe path in archive: %s", rel)
		}
	}
	return filepath.Join(base, filepath.FromSlash(rel)), nil
}

func extractZip(packagePath, destDir string) error {
	r, err := zip.OpenReader(packagePath)
	if err != nil {
		return err
	}
	defer r.Close()

	for _, f := range r.File {
		name := strings.ReplaceAll(f.Name, "\\", "/")
		target, err := safeJoin(destDir, name)
		if err != nil {
			return err
		}

		if f.FileInfo().IsDir() {
			if err := os.MkdirAll(target, 0755); err != nil {
				return err
			}
			continue
		}

		if err := os.MkdirAll(filepath.Dir(target), 0755); err != nil {
			return err
		}

		rc, err := f.Open()
		if err != nil {
			return err
		}

		out, err := os.OpenFile(target, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0644)
		if err != nil {
			rc.Close()
			return err
		}

		_, copyErr := io.Copy(out, rc)
		rc.Close()
		out.Close()
		if copyErr != nil {
			return copyErr
		}
	}

	return nil
}

func extractWithLibarchive(packagePath, destDir string) error {
	cPath := C.CString(packagePath)
	defer C.free(unsafe.Pointer(cPath))

	a := C.archive_read_new()
	if a == nil {
		return fmt.Errorf("failed to allocate archive reader")
	}
	defer C.archive_read_free(a)

	C.archive_read_support_format_all(a)
	C.archive_read_support_filter_all(a)

	if r := C.archive_read_open_filename(a, cPath, 10240); r != C.ARCHIVE_OK {
		return fmt.Errorf("failed to open archive %s: %s", packagePath, C.GoString(C.archive_error_string(a)))
	}

	var entry *C.struct_archive_entry
	for {
		r := C.archive_read_next_header(a, &entry)
		if r == C.ARCHIVE_EOF {
			break
		}
		if r != C.ARCHIVE_OK {
			return fmt.Errorf("failed to read archive entry: %s", C.GoString(C.archive_error_string(a)))
		}

		entryPathname := C.GoString(C.archive_entry_pathname(entry))
		target, err := safeJoin(destDir, entryPathname)
		if err != nil {
			return err
		}

		filetype := C.archive_entry_filetype(entry)
		if filetype == C.AE_IFDIR {
			if err := os.MkdirAll(target, 0755); err != nil {
				return err
			}
			continue
		}

		if err := os.MkdirAll(filepath.Dir(target), 0755); err != nil {
			return err
		}

		out, err := os.OpenFile(target, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0644)
		if err != nil {
			return err
		}

		expectedSize := int64(C.archive_entry_size(entry))
		written := int64(0)
		buf := make([]byte, 1<<20)

		for {
			n := int64(C.archive_read_data(a, unsafe.Pointer(&buf[0]), C.size_t(len(buf))))
			if n < 0 {
				errMsg := C.GoString(C.archive_error_string(a))
				if written == expectedSize {
					logWarn("ignoring libarchive CRC mismatch for [%s]: got all %d expected bytes anyway", entryPathname, expectedSize)
					break
				}
				out.Close()
				return fmt.Errorf("failed to read data for [%s]: %s", entryPathname, errMsg)
			}
			if n == 0 {
				break
			}
			if _, werr := out.Write(buf[:n]); werr != nil {
				out.Close()
				return werr
			}
			written += n
		}

		out.Close()
	}

	return nil
}

var specialCaseDirs = map[string]bool{
	"data": true, "skse": true, "interface": true, "meshes": true, "misc": true,
	"music": true, "scripts": true, "seq": true, "shadersfx": true, "sound": true,
	"strings": true, "textures": true, "video": true, "fomod": true,
}

func packageUnzippedInTempDir(packagePath string) (tempDir string, paths []string, cleanup func(), err error) {
	root, err := os.MkdirTemp("", "skrim-*")
	if err != nil {
		return "", nil, nil, err
	}
	cleanup = func() { os.RemoveAll(root) }
	tempDir = root

	ext := strings.ToLower(filepath.Ext(packagePath))
	if ext == ".7z" || ext == ".rar" {
		if err = extractWithLibarchive(packagePath, tempDir); err != nil {
			cleanup()
			return "", nil, nil, err
		}
	} else {
		if err = extractZip(packagePath, tempDir); err != nil {
			cleanup()
			return "", nil, nil, err
		}
	}

	entries, err := os.ReadDir(tempDir)
	if err != nil {
		cleanup()
		return "", nil, nil, err
	}
	if len(entries) == 1 && entries[0].IsDir() && !specialCaseDirs[strings.ToLower(entries[0].Name())] {
		tempDir = filepath.Join(tempDir, entries[0].Name())
	}

	err = filepath.WalkDir(tempDir, func(p string, d os.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if d.IsDir() {
			return nil
		}
		rel, relErr := filepath.Rel(tempDir, p)
		if relErr != nil {
			return relErr
		}
		paths = append(paths, filepath.ToSlash(rel))
		return nil
	})
	if err != nil {
		cleanup()
		return "", nil, nil, err
	}

	return tempDir, paths, cleanup, nil
}

type xmlNode struct {
	XMLName  xml.Name
	Attrs    []xml.Attr `xml:",any,attr"`
	Text     string     `xml:",chardata"`
	Children []xmlNode  `xml:",any"`
}

func (n *xmlNode) attr(name string) (string, bool) {
	for _, a := range n.Attrs {
		if a.Name.Local == name {
			return a.Value, true
		}
	}
	return "", false
}

func (n *xmlNode) attrOr(name, def string) string {
	if v, ok := n.attr(name); ok {
		return v
	}
	return def
}

func (n *xmlNode) find(path string) *xmlNode {
	path = strings.TrimPrefix(path, "./")
	parts := strings.Split(path, "/")
	current := n
	for _, part := range parts {
		found := false
		for i := range current.Children {
			if current.Children[i].XMLName.Local == part {
				current = &current.Children[i]
				found = true
				break
			}
		}
		if !found {
			return nil
		}
	}
	return current
}

func (n *xmlNode) findAll(path string) []*xmlNode {
	path = strings.TrimPrefix(path, "./")
	parts := strings.Split(path, "/")
	current := []*xmlNode{n}
	for _, part := range parts {
		var next []*xmlNode
		for _, c := range current {
			for i := range c.Children {
				if c.Children[i].XMLName.Local == part {
					next = append(next, &c.Children[i])
				}
			}
		}
		current = next
	}
	return current
}

func (n *xmlNode) findText(path, def string) string {
	found := n.find(path)
	if found == nil {
		return def
	}
	return strings.TrimSpace(found.Text)
}

func decodeXMLBytes(data []byte) string {
	switch {
	case len(data) >= 2 && data[0] == 0xff && data[1] == 0xfe:
		u16 := make([]uint16, (len(data)-2)/2)
		for i := range u16 {
			u16[i] = uint16(data[2+2*i]) | uint16(data[3+2*i])<<8
		}
		return string(utf16.Decode(u16))
	case len(data) >= 2 && data[0] == 0xfe && data[1] == 0xff:
		u16 := make([]uint16, (len(data)-2)/2)
		for i := range u16 {
			u16[i] = uint16(data[2+2*i])<<8 | uint16(data[3+2*i])
		}
		return string(utf16.Decode(u16))
	case len(data) >= 3 && data[0] == 0xef && data[1] == 0xbb && data[2] == 0xbf:
		return string(data[3:])
	default:
		return string(data)
	}
}

func parseXML(text string) (*xmlNode, error) {
	decoder := xml.NewDecoder(strings.NewReader(text))
	decoder.CharsetReader = func(charset string, input io.Reader) (io.Reader, error) {
		return input, nil
	}
	decoder.Strict = false

	var root xmlNode
	if err := decoder.Decode(&root); err != nil {
		return nil, err
	}
	return &root, nil
}

func loadFomodConfig(tempDir string, paths []string) (*xmlNode, error) {
	var fomodPath string
	for _, p := range paths {
		parts := strings.Split(p, "/")
		name := parts[len(parts)-1]
		if strings.ToLower(name) == "moduleconfig.xml" && len(parts) >= 2 && strings.ToLower(parts[len(parts)-2]) == "fomod" {
			fomodPath = p
			break
		}
	}

	if fomodPath == "" {
		return nil, nil
	}

	data, err := os.ReadFile(filepath.Join(tempDir, filepath.FromSlash(fomodPath)))
	if err != nil {
		return nil, err
	}

	return parseXML(decodeXMLBytes(data))
}

func recommendedPluginIndex(plugins []*xmlNode, skyrimVersion *string) *int {
	if skyrimVersion == nil {
		return nil
	}
	detected := parseVersionParts(*skyrimVersion)

	var bestIndex *int
	var bestThreshold []int

	for i, plugin := range plugins {
		type applicablePair struct {
			threshold []int
			typeName  string
		}
		var applicable []applicablePair

		for _, pattern := range plugin.findAll("typeDescriptor/dependencyType/patterns/pattern") {
			gameDependency := pattern.find("dependencies/gameDependency")
			if gameDependency == nil {
				continue
			}
			versionAttr, _ := gameDependency.attr("version")
			threshold := parseVersionParts(versionAttr)
			if compareVersions(detected, threshold) >= 0 {
				typeNode := pattern.find("type")
				typeName, _ := typeNode.attr("name")
				applicable = append(applicable, applicablePair{threshold, typeName})
			}
		}

		if len(applicable) == 0 {
			continue
		}

		best := applicable[0]
		for _, p := range applicable[1:] {
			if compareVersions(p.threshold, best.threshold) > 0 {
				best = p
			}
		}

		if best.typeName == "Recommended" && (bestThreshold == nil || compareVersions(best.threshold, bestThreshold) > 0) {
			index := i + 1
			bestIndex = &index
			bestThreshold = best.threshold
		}
	}

	return bestIndex
}

func installedPluginFiles(gameDir string) map[string]bool {
	dataDir := filepath.Join(gameDir, "Data")
	entries, err := os.ReadDir(dataDir)
	if err != nil {
		return map[string]bool{}
	}

	result := map[string]bool{}
	for _, e := range entries {
		ext := strings.ToLower(filepath.Ext(e.Name()))
		if ext == ".esp" || ext == ".esm" || ext == ".esl" {
			result[strings.ToLower(e.Name())] = true
		}
	}
	return result
}

func fomodDependenciesMet(dependencies *xmlNode, flags map[string]string, dataFiles map[string]bool) bool {
	var results []bool

	for i := range dependencies.Children {
		dep := &dependencies.Children[i]
		switch dep.XMLName.Local {
		case "flagDependency":
			flagName, _ := dep.attr("flag")
			expected, _ := dep.attr("value")
			current := flags[flagName]
			results = append(results, current == expected || (expected == "Off" && current == ""))
		case "fileDependency":
			fileAttr, _ := dep.attr("file")
			stateAttr, _ := dep.attr("state")
			present := dataFiles[strings.ToLower(fileAttr)]
			if stateAttr == "Missing" {
				results = append(results, !present)
			} else {
				results = append(results, present)
			}
		case "gameDependency":
			results = append(results, true)
		case "dependencies":
			results = append(results, fomodDependenciesMet(dep, flags, dataFiles))
		}
	}

	operator := dependencies.attrOr("operator", "And")
	if operator == "And" {
		for _, r := range results {
			if !r {
				return false
			}
		}
		return true
	}
	for _, r := range results {
		if r {
			return true
		}
	}
	return false
}

func resolvePluginType(plugin *xmlNode, flags map[string]string, dataFiles map[string]bool) string {
	if staticType := plugin.find("typeDescriptor/type"); staticType != nil {
		name, _ := staticType.attr("name")
		return name
	}

	dependencyType := plugin.find("typeDescriptor/dependencyType")
	if dependencyType == nil {
		return "Optional"
	}

	for _, pattern := range dependencyType.findAll("patterns/pattern") {
		deps := pattern.find("dependencies")
		if deps != nil && fomodDependenciesMet(deps, flags, dataFiles) {
			typeNode := pattern.find("type")
			name, _ := typeNode.attr("name")
			return name
		}
	}

	defaultType := dependencyType.find("defaultType")
	if defaultType != nil {
		name, _ := defaultType.attr("name")
		return name
	}
	return "Optional"
}

func promptLine(prompt string) string {
	fmt.Print(prompt)
	line, err := stdinReader.ReadString('\n')
	if err != nil && line == "" {
		fmt.Fprintln(os.Stderr, "ERROR: unexpected end of input")
		os.Exit(1)
	}
	return strings.TrimSpace(line)
}

func containsStr(list []string, target string) bool {
	for _, item := range list {
		if item == target {
			return true
		}
	}
	return false
}

func allIn(items, universe []string) bool {
	set := map[string]bool{}
	for _, u := range universe {
		set[u] = true
	}
	for _, item := range items {
		if !set[item] {
			return false
		}
	}
	return true
}

func allValidIndices(strs []string, max int) bool {
	for _, s := range strs {
		n, err := strconv.Atoi(s)
		if err != nil || n < 1 || n > max {
			return false
		}
	}
	return true
}

func asStringSlice(v any) ([]string, bool) {
	if s, ok := v.([]string); ok {
		return s, true
	}
	list, ok := v.([]any)
	if !ok {
		return nil, false
	}
	result := make([]string, len(list))
	for i, item := range list {
		s, ok := item.(string)
		if !ok {
			return nil, false
		}
		result[i] = s
	}
	return result, true
}

func calculateFomodChoices(fomodConfig *xmlNode, oldChoices map[string]any, skyrimVersion *string, gameDir string) map[string]any {
	if oldChoices == nil {
		oldChoices = map[string]any{}
	}
	newChoices := map[string]any{}
	flags := map[string]string{}
	dataFiles := map[string]bool{}
	if gameDir != "" {
		dataFiles = installedPluginFiles(gameDir)
	}

	for _, step := range fomodConfig.findAll("installSteps/installStep") {
		visible := step.find("visible/dependencies")
		if visible != nil && !fomodDependenciesMet(visible, flags, dataFiles) {
			continue
		}

		for _, group := range step.findAll("optionalFileGroups/group") {
			groupType, _ := group.attr("type")
			switch groupType {
			case "SelectExactlyOne", "SelectAny", "SelectAtMostOne", "SelectAll":
			default:
				panic(fmt.Sprintf("fomod group type not supported yet: %s", groupType))
			}

			groupName, _ := group.attr("name")
			plugins := group.findAll("plugins/plugin")
			pluginNames := make([]string, len(plugins))
			for i, p := range plugins {
				name, _ := p.attr("name")
				pluginNames[i] = name
			}

			var chosen any

			switch groupType {
			case "SelectAll":
				chosen = pluginNames

			case "SelectAny", "SelectAtMostOne":
				limit := 1
				if groupType == "SelectAny" {
					limit = len(plugins)
				}

				remembered, hasRemembered := asStringSlice(oldChoices[groupName])
				valid := hasRemembered && len(remembered) <= limit && allIn(remembered, pluginNames)

				var picks []string
				if valid {
					picks = remembered
				} else {
					pluginTypes := map[string]string{}
					for _, p := range plugins {
						name, _ := p.attr("name")
						pluginTypes[name] = resolvePluginType(p, flags, dataFiles)
					}

					var available []*xmlNode
					for _, p := range plugins {
						name, _ := p.attr("name")
						if pluginTypes[name] != "NotUsable" {
							available = append(available, p)
						}
					}

					var defaults []string
					for _, p := range available {
						name, _ := p.attr("name")
						t := pluginTypes[name]
						if t == "Required" || t == "Recommended" {
							defaults = append(defaults, name)
						}
					}

					if groupType == "SelectAtMostOne" && len(defaults) > 1 {
						defaults = nil
					}

					if len(available) == 0 {
						picks = []string{}
					} else {
						label := "select any"
						if groupType == "SelectAtMostOne" {
							label = "select at most one"
						}
						fmt.Printf("\n%s (%s):\n", groupName, label)
						for i, p := range available {
							name, _ := p.attr("name")
							description := p.findText("description", "")
							marker := ""
							if containsStr(defaults, name) {
								marker = " (recommended)"
							}
							fmt.Printf("  %d) %s%s\n", i+1, name, marker)
							if description != "" {
								fmt.Printf("     %s\n", description)
							}
						}

						defaultPrompt := "blank for none"
						if len(defaults) > 0 {
							defaultPrompt = "default " + strings.Join(defaults, ", ")
						}

						for {
							choice := promptLine(fmt.Sprintf("Choices [1-%d, comma-separated, %s]: ", len(available), defaultPrompt))
							if choice == "" {
								picks = append([]string{}, defaults...)
								break
							}

							indexStrs := strings.Split(choice, ",")
							for i := range indexStrs {
								indexStrs[i] = strings.TrimSpace(indexStrs[i])
							}

							if len(indexStrs) <= limit && allValidIndices(indexStrs, len(available)) {
								picks = nil
								for _, idxStr := range indexStrs {
									idx, _ := strconv.Atoi(idxStr)
									name, _ := available[idx-1].attr("name")
									picks = append(picks, name)
								}
								break
							}

							if groupType == "SelectAtMostOne" {
								fmt.Printf("Please enter at most one number between 1 and %d.\n", len(available))
							} else {
								fmt.Printf("Please enter numbers between 1 and %d, comma-separated.\n", len(available))
							}
						}
					}
				}

				chosen = picks

			default:
				remembered, hasRemembered := oldChoices[groupName].(string)
				if hasRemembered && containsStr(pluginNames, remembered) {
					chosen = remembered
				} else {
					pluginTypes := map[string]string{}
					for _, p := range plugins {
						name, _ := p.attr("name")
						pluginTypes[name] = resolvePluginType(p, flags, dataFiles)
					}

					var typeRecommended []int
					for i, p := range plugins {
						name, _ := p.attr("name")
						t := pluginTypes[name]
						if t == "Required" || t == "Recommended" {
							typeRecommended = append(typeRecommended, i+1)
						}
					}

					var defaultIndex *int
					if len(typeRecommended) == 1 {
						idx := typeRecommended[0]
						defaultIndex = &idx
					} else {
						defaultIndex = recommendedPluginIndex(plugins, skyrimVersion)
					}

					fmt.Printf("\n%s:\n", groupName)
					for i, p := range plugins {
						name, _ := p.attr("name")
						description := p.findText("description", "")
						marker := ""
						if defaultIndex != nil && i+1 == *defaultIndex {
							marker = " (default)"
						}
						fmt.Printf("  %d) %s%s\n", i+1, name, marker)
						if description != "" {
							fmt.Printf("     %s\n", description)
						}
					}

					prompt := fmt.Sprintf("Choice [1-%d]", len(plugins))
					if defaultIndex != nil {
						prompt += fmt.Sprintf(", default %d", *defaultIndex)
					}
					prompt += ": "

					var choiceIndex int
					for {
						choiceStr := promptLine(prompt)
						if choiceStr == "" && defaultIndex != nil {
							choiceStr = strconv.Itoa(*defaultIndex)
						}

						n, err := strconv.Atoi(choiceStr)
						if err == nil && n >= 1 && n <= len(plugins) {
							choiceIndex = n
							break
						}

						fmt.Printf("Please enter a number between 1 and %d.\n", len(plugins))
					}

					name, _ := plugins[choiceIndex-1].attr("name")
					chosen = name
				}
			}

			newChoices[groupName] = chosen

			chosenSet := map[string]bool{}
			if list, ok := chosen.([]string); ok {
				for _, n := range list {
					chosenSet[n] = true
				}
			} else if s, ok := chosen.(string); ok {
				chosenSet[s] = true
			}

			for _, p := range plugins {
				name, _ := p.attr("name")
				if chosenSet[name] {
					for _, flag := range p.findAll("conditionFlags/flag") {
						flagName, _ := flag.attr("name")
						flags[flagName] = strings.TrimSpace(flag.Text)
					}
				}
			}
		}
	}

	return newChoices
}

func splitPathParts(p string) []string {
	if p == "" || p == "." {
		return nil
	}
	return strings.Split(p, "/")
}

func lowerAll(items []string) []string {
	result := make([]string, len(items))
	for i, s := range items {
		result[i] = strings.ToLower(s)
	}
	return result
}

func equalPrefix(a, b []string) bool {
	if len(a) < len(b) {
		return false
	}
	for i := range b {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

func equalStrings(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

func calculateFomodTargets(fomodConfig *xmlNode, choices map[string]any, paths []string, gameDir string) [][2]string {
	matched := func(source, destination string) [][2]string {
		sourceParts := lowerAll(splitPathParts(strings.ReplaceAll(source, "\\", "/")))
		var destParts []string
		if destination != "" {
			destParts = splitPathParts(strings.ReplaceAll(destination, "\\", "/"))
		}

		var pairs [][2]string
		for _, p := range paths {
			pParts := strings.Split(p, "/")
			pPartsLower := lowerAll(pParts)
			if !equalPrefix(pPartsLower, sourceParts) {
				continue
			}
			tail := pParts[len(sourceParts):]
			dstParts := append([]string{"Data"}, destParts...)
			dstParts = append(dstParts, tail...)
			pairs = append(pairs, [2]string{p, strings.Join(dstParts, "/")})
		}
		return pairs
	}

	matchedFile := func(source, destination string) [][2]string {
		sourceParts := lowerAll(splitPathParts(strings.ReplaceAll(source, "\\", "/")))
		var destParts []string
		if destination != "" {
			destParts = splitPathParts(strings.ReplaceAll(destination, "\\", "/"))
		} else {
			destParts = splitPathParts(strings.ReplaceAll(source, "\\", "/"))
		}

		for _, p := range paths {
			pParts := strings.Split(p, "/")
			if equalStrings(lowerAll(pParts), sourceParts) {
				dstParts := append([]string{"Data"}, destParts...)
				return [][2]string{{p, strings.Join(dstParts, "/")}}
			}
		}
		return nil
	}

	var targets [][2]string
	flags := map[string]string{}
	dataFiles := map[string]bool{}
	if gameDir != "" {
		dataFiles = installedPluginFiles(gameDir)
	}

	for _, folder := range fomodConfig.findAll("requiredInstallFiles/folder") {
		source, _ := folder.attr("source")
		dest := folder.attrOr("destination", "")
		targets = append(targets, matched(source, dest)...)
	}

	for _, file := range fomodConfig.findAll("requiredInstallFiles/file") {
		source, _ := file.attr("source")
		dest := file.attrOr("destination", "")
		targets = append(targets, matchedFile(source, dest)...)
	}

	for _, step := range fomodConfig.findAll("installSteps/installStep") {
		visible := step.find("visible/dependencies")
		if visible != nil && !fomodDependenciesMet(visible, flags, dataFiles) {
			continue
		}

		for _, group := range step.findAll("optionalFileGroups/group") {
			groupName, _ := group.attr("name")
			chosen := choices[groupName]
			var chosenNames []string
			switch c := chosen.(type) {
			case string:
				chosenNames = []string{c}
			case []string:
				chosenNames = c
			}

			plugins := group.findAll("plugins/plugin")
			var chosenPlugins []*xmlNode
			for _, p := range plugins {
				name, _ := p.attr("name")
				if containsStr(chosenNames, name) {
					chosenPlugins = append(chosenPlugins, p)
				}
			}

			for _, cp := range chosenPlugins {
				for _, folder := range cp.findAll("files/folder") {
					source, _ := folder.attr("source")
					dest := folder.attrOr("destination", "")
					targets = append(targets, matched(source, dest)...)
				}
				for _, file := range cp.findAll("files/file") {
					source, _ := file.attr("source")
					dest := file.attrOr("destination", "")
					targets = append(targets, matchedFile(source, dest)...)
				}
				for _, flag := range cp.findAll("conditionFlags/flag") {
					flagName, _ := flag.attr("name")
					flags[flagName] = strings.TrimSpace(flag.Text)
				}
			}
		}
	}

	for _, pattern := range fomodConfig.findAll("conditionalFileInstalls/patterns/pattern") {
		deps := pattern.find("dependencies")
		if deps == nil || !fomodDependenciesMet(deps, flags, dataFiles) {
			continue
		}

		for _, folder := range pattern.findAll("files/folder") {
			source, _ := folder.attr("source")
			dest := folder.attrOr("destination", "")
			targets = append(targets, matched(source, dest)...)
		}
		for _, file := range pattern.findAll("files/file") {
			source, _ := file.attr("source")
			dest := file.attrOr("destination", "")
			targets = append(targets, matchedFile(source, dest)...)
		}
	}

	return targets
}
