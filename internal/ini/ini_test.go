package ini_test

import (
	"reflect"
	"skrim/internal/ini"
	"testing"
)

func TestParseString(t *testing.T) {
	type testCase struct {
		name     string
		input    string
		expected ini.Data
	}

	cases := []testCase{
		{
			name: "should parse sections",
			input: `
[fruit]
[ vegetables ]
[desserts]
`,
			expected: ini.Data{
				[]ini.Section{
					ini.Section{Name: "fruit"},
					ini.Section{Name: "vegetables"},
					ini.Section{Name: "desserts"},
				},
			},
		},
		{
			name: "should parse fields",
			input: `
[candy]
tasty = yes
healthy = no

[vegetables]
tasty = yes
healthy= hell yes
`,
			expected: ini.Data{
				[]ini.Section{
					ini.Section{
						Name: "candy",
						Fields: []ini.Field{
							ini.Field{Key: "tasty", Value: "yes"},
							ini.Field{Key: "healthy", Value: "no"},
						},
					},
					ini.Section{
						Name: "vegetables",
						Fields: []ini.Field{
							ini.Field{Key: "tasty", Value: "yes"},
							ini.Field{Key: "healthy", Value: "hell yes"},
						},
					},
				},
			},
		},
		{
			name: "should ignore fields without sections",
			input: `
what = no
sure? = yes

[vegetables]
tasty = yes
healthy= hell yes
`,
			expected: ini.Data{
				[]ini.Section{
					ini.Section{
						Name: "vegetables",
						Fields: []ini.Field{
							ini.Field{Key: "tasty", Value: "yes"},
							ini.Field{Key: "healthy", Value: "hell yes"},
						},
					},
				},
			},
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			actual := ini.ParseString(tc.input)

			if !reflect.DeepEqual(actual, tc.expected) {
				t.Errorf("expected = %v, actual = %v", tc.expected, actual)
			}
		})
	}
}
