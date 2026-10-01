package ini_test

import (
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"skrim/internal/ini"
	"testing"
)

type testCase struct {
	name     string
	content  string
	expected ini.Data
}

var testCases = []testCase{
	{
		name: "should parse sections",
		content: `
[fruit]
[ vegetables ]
[desserts]
`,
		expected: ini.Data{
			[]ini.Section{
				{Name: "fruit"},
				{Name: "vegetables"},
				{Name: "desserts"},
			},
		},
	},
	{
		name: "should parse fields",
		content: `
[candy]
tasty = yes
healthy = no

[vegetables]
tasty = yes
healthy= hell yes
`,
		expected: ini.Data{
			[]ini.Section{
				{
					Name: "candy",
					Fields: []ini.Field{
						{Key: "tasty", Value: "yes"},
						{Key: "healthy", Value: "no"},
					},
				},
				{
					Name: "vegetables",
					Fields: []ini.Field{
						{Key: "tasty", Value: "yes"},
						{Key: "healthy", Value: "hell yes"},
					},
				},
			},
		},
	},
	{
		name: "should ignore fields without sections",
		content: `
what = no
sure? = yes

[vegetables]
tasty = yes
healthy= hell yes
`,
		expected: ini.Data{
			[]ini.Section{
				{
					Name: "vegetables",
					Fields: []ini.Field{
						{Key: "tasty", Value: "yes"},
						{Key: "healthy", Value: "hell yes"},
					},
				},
			},
		},
	},
	{
		name: "should cast fields without values as empty strings",
		content: `
[vegetables]
tasty = yes
healthy=
`,
		expected: ini.Data{
			[]ini.Section{
				{
					Name: "vegetables",
					Fields: []ini.Field{
						{Key: "tasty", Value: "yes"},
						{Key: "healthy", Value: ""},
					},
				},
			},
		},
	},
	{
		name: "should ignore comments",
		content: `
[fruit]
[vegetables]
#[poison]
[desserts]
# poison=yes
`,
		expected: ini.Data{
			[]ini.Section{
				{Name: "fruit"},
				{Name: "vegetables"},
				{Name: "desserts"},
			},
		},
	},
}

func TestParseString(t *testing.T) {
	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			actual := *ini.ParseString(tc.content)

			if !reflect.DeepEqual(actual, tc.expected) {
				t.Errorf("expected = %v, actual = %v", tc.expected, actual)
			}
		})
	}
}

func TestParseFile(t *testing.T) {
	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			// write content to a tempfile
			configPath := filepath.Join(t.TempDir(), "test.ini")
			err := os.WriteFile(configPath, []byte(tc.content), 0644)
			if err != nil {
				t.Errorf("could not write test.ini: %v", err)
			}

			// read it with the library
			actual, err := ini.ParseFile(configPath)

			// make sure there was no error
			if err != nil {
				t.Errorf("could not write test.ini: %v", err)
			}

			// compare to the test case
			if !reflect.DeepEqual(*actual, tc.expected) {
				t.Errorf("expected = %v, actual = %v", tc.expected, actual)
			}
		})
	}

	// test nonexistent file
	_, err := ini.ParseFile("does-not-exist.txt")
	if !errors.Is(err, os.ErrNotExist) {
		t.Errorf("expected file not found error, got %v", err)
	}
}
