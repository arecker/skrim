package ini_test

import (
	"errors"
	"os"
	"path/filepath"
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
			Sections: []ini.Section{
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
			Sections: []ini.Section{
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
		name: "should cast fields without values as empty strings",
		content: `
[vegetables]
tasty = yes
healthy=
`,
		expected: ini.Data{
			Sections: []ini.Section{
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
			Sections: []ini.Section{
				{Name: "fruit"},
				{Name: "vegetables"},
				{Name: "desserts"},
			},
		},
	},
}

func compareSections(t *testing.T, actual []ini.Section, expected []ini.Section) {
	// compare length
	if len(actual) != len(expected) {
		t.Errorf(
			"actual has %d sections, expected has %d sections",
			len(actual), len(expected),
		)
		return
	}

	for i := range expected {
		compareSection(t, actual[i], expected[i])
	}
}

func compareSection(t *testing.T, actual ini.Section, expected ini.Section) {
	// compare names
	if actual.Name != expected.Name {
		t.Errorf("names don't match: actual = %s, expected = %s", actual.Name, expected.Name)
	}

	// compare fields
	for i := range expected.Fields {
		compareField(t, actual.Fields[i], expected.Fields[i])
	}
}

func compareField(t *testing.T, actual ini.Field, expected ini.Field) {
	if actual.Key != expected.Key || actual.Value != expected.Value {
		t.Errorf(
			"fields do not match: actual = %v, expected = %v",
			actual, expected,
		)
	}
}

func TestParseString(t *testing.T) {
	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			actual := *ini.ParseString(tc.content)
			compareSections(t, actual.Sections, tc.expected.Sections)
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
			compareSections(t, actual.Sections, tc.expected.Sections)
		})
	}

	// test nonexistent file
	_, err := ini.ParseFile("does-not-exist.txt")
	if !errors.Is(err, os.ErrNotExist) {
		t.Errorf("expected file not found error, got %v", err)
	}
}

func TestDataGet(t *testing.T) {
	// parse data
	data := ini.ParseString(`
[skrim]
option_1 = yes
option_2 = maybe
`)

	if data == nil {
		t.Errorf("TestDataGet() didn't return data!")
	}

	expected := ini.Section{
		Name: "skrim",
		Fields: []ini.Field{
			{Key: "option_1", Value: "yes"},
			{Key: "option_2", Value: "maybe"},
		},
	}

	// no match should return nil
	if result := data.Get("blah"); result != nil {
		t.Errorf(
			"TestDataGet() didn't return section, actual = %v, expected = %v",
			result, expected,
		)
	}

	// fetch the section
	actual := data.Get("skrim")

	// compare
	compareSection(t, *actual, expected)

	// maybe i'm ignorant and this is just how go works, but makes
	// sure that modifying the section updates the actual data
	actual.Name = "new name"

	if data.Sections[0].Name != actual.Name {
		t.Errorf(
			"TestDataGet() changes did not persist, actual = %v, expected = %v",
			data.Sections[0].Name, actual.Name,
		)
	}
}

func TestDataPut(t *testing.T) {
	data := ini.ParseString(`
[fruit]
tasty = yes
healthy = yes

[candy]
tasty = no
`)

	data.Put("candy", "tasty", "yes")
	data.Put("candy", "healthy", "no")
	data.Put("fish", "healthy", "yes")
	data.Put("fish", "tasty", "no")

	expected := ini.Data{
		Sections: []ini.Section{
			{
				Name: "fruit",
				Fields: []ini.Field{
					{Key: "tasty", Value: "yes"},
					{Key: "healthy", Value: "yes"},
				},
			},
			{
				Name: "candy",
				Fields: []ini.Field{
					{Key: "tasty", Value: "yes"},
					{Key: "healthy", Value: "no"},
				},
			},
			{
				Name: "fish",
				Fields: []ini.Field{
					{Key: "healthy", Value: "yes"},
					{Key: "tasty", Value: "no"},
				},
			},
		},
	}

	compareSections(t, data.Sections, expected.Sections)
}

// func TestDataString(t *testing.T) {
//	type configPatch struct {
//		sectionName string
//		fieldKey    string
//		fieldValue  string
//	}

//	type testCase struct {
//		name     string
//		original string
//		patches  []configPatch
//		expected string
//	}

//	testCases := []testCase{
//		{
//			name:     "add to a blank config",
//			original: "",
//			patches:  []configPatch{{"main", "working", "yes"}},
//			expected: strings.TrimSpace(`
// [main]
// working = yes
// `),
//		},
//	}

//	for _, tc := range testCases {
//		t.Run(tc.name, func(t *testing.T) {
//			data := ini.ParseString(tc.original)
//			for _, p := range tc.patches {
//				data.Put(p.sectionName, p.fieldKey, p.fieldValue)
//			}
//			actual := data.String()

//			if actual != tc.expected {
//				t.Errorf("actual = %v, expected = %v", actual, tc.expected)
//			}
//		})
//	}
// }
