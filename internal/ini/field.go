package ini

import (
	"regexp"
	"strings"
)

type Field struct {
	Key           string
	Value         string
	captureGroups []string
}

func fieldPattern() *regexp.Regexp {
	return regexp.MustCompile(`^(\s*)([^=\s]*)(\s*)=(\s*)([^#]*?)(\s*)(#.*)?$`)
}

func FindField(line string) *Field {
	if matches := fieldPattern().FindStringSubmatch(line); matches != nil {
		// extract key/value
		key := matches[2]
		value := matches[5]

		// return a new Field
		return &Field{Key: key, Value: value, captureGroups: matches}
	}

	return nil
}

func (f *Field) String() string {
	var sb strings.Builder
	sb.WriteString(f.captureGroups[1])
	sb.WriteString(f.Key) // swap out group #2
	sb.WriteString(f.captureGroups[3])
	sb.WriteString("=")
	sb.WriteString(f.captureGroups[4])
	sb.WriteString(f.Value) // swap out group #5
	sb.WriteString(f.captureGroups[6])
	sb.WriteString(f.captureGroups[7])
	return sb.String()
}
