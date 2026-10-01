package ini

import (
	"os"
	"regexp"
	"strings"
)

type Data struct {
	Sections []Section
}

type Section struct {
	Name   string
	Fields []Field
}

type Field struct {
	Key   string
	Value string
}

// Parse a string into ini data sections
func ParseString(content string) *Data {
	// [<name>]
	re_sec := regexp.MustCompile(`\[([^]]+)\]`)
	// <key> = <value>
	re_field := regexp.MustCompile(`^([^=]+)\s*=\s*(.*)$`)

	sections := []Section{}
	var curSection *Section

	for line := range strings.SplitSeq(content, "\n") {
		if isCommented(line) {
			continue
		}

		// check for [section]
		if matches := re_sec.FindStringSubmatch(line); matches != nil {
			// extract the name
			name := strings.TrimSpace(matches[1])

			// if we have a current section, add it
			if curSection != nil {
				sections = append(sections, *curSection)
			}

			// assign it to the new current section
			curSection = &Section{Name: name}
		}

		// check for key=val field
		if matches := re_field.FindStringSubmatch(line); matches != nil {
			// extract key/value
			key := strings.TrimSpace(matches[1])
			value := strings.TrimSpace(matches[2])
			// add Field to current section
			if curSection != nil {
				field := Field{Key: key, Value: value}
				curSection.Fields = append(curSection.Fields, field)
			}
		}
	}

	// append the final section
	sections = append(sections, *curSection)

	// done!
	return &Data{Sections: sections}
}

func ParseFile(path string) (*Data, error) {
	content, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	return ParseString(string(content)), nil
}

func isCommented(line string) bool {
	return strings.HasPrefix(strings.TrimSpace(line), "#")
}
