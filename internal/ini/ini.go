package ini

import (
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

// Parse a string into ini data
func ParseString(content string) Data {
	data := Data{}
	sections := []Section{}

	// [<name>]
	re_sec := regexp.MustCompile(`\[([^]]+)\]`)
	// <key> = <value>
	re_field := regexp.MustCompile(`^([^=]+)\s*=\s*(.*)$`)

	var curSection *Section

	for _, line := range strings.Split(content, "\n") {
		// check for [section]
		if matches := re_sec.FindStringSubmatch(line); matches != nil {
			// extract the name
			name := strings.TrimSpace(matches[1])

			// if we have a current section, add it, we're done
			if curSection != nil {
				sections = append(sections, *curSection)
			}

			// assign it to the current section
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

	// assign our sections to the data
	data.Sections = sections

	// done!
	return data
}
