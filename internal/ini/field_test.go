package ini_test

import (
	"skrim/internal/ini"
	"testing"
)

func TestFindField(t *testing.T) {
	testCases := []struct {
		name          string
		line          string
		expectedKey   string
		expectedValue string
	}{
		{
			name:          "no spaces",
			line:          "a=b",
			expectedKey:   "a",
			expectedValue: "b",
		},
		{
			name:          "some spaces",
			line:          "a = b",
			expectedKey:   "a",
			expectedValue: "b",
		},
		{
			name:          "lotsa spaces",
			line:          "  a  =  b ",
			expectedKey:   "a",
			expectedValue: "b",
		},
		{
			name:          "trailing comment",
			line:          "a = b # buttlicker",
			expectedKey:   "a",
			expectedValue: "b",
		},
		{
			name:          "double equals",
			line:          "a = this is an equals = ",
			expectedKey:   "a",
			expectedValue: "this is an equals = ",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			result := ini.FindField(tc.line)
			if result.Key != tc.expectedKey {
				t.Errorf("actual = %v, expected = %v", result.Key, tc.expectedKey)
			}
		})
	}
}

func TestFieldString(t *testing.T) {
	testCases := []struct {
		name        string
		input       string
		changeKey   string
		changeValue string
		expected    string
	}{
		{
			name:     "no updates",
			input:    "a = b",
			expected: "a = b",
		},
		{
			name:     "no updates compound word",
			input:    "a = b c d",
			expected: "a = b c d",
		},
		{
			name:      "update key",
			input:     "a = b",
			changeKey: "apples",
			expected:  "apples = b",
		},
		{
			name:        "update value",
			input:       "a = b",
			changeValue: "apples",
			expected:    "a = apples",
		},
		{
			name:      "update key with comment",
			input:     "a = b  # this is a comment",
			changeKey: "apples",
			expected:  "apples = b  # this is a comment",
		},
		{
			name:        "update value with comment",
			input:       "a = b  # this is a comment",
			changeValue: "apples",
			expected:    "a = apples  # this is a comment",
		},
		{
			name:        "update value with trailing spaces",
			input:       "a = b   ",
			changeValue: "apples",
			expected:    "a = apples   ",
		},
		{
			name:        "update value with equals in original",
			input:       "a = b=c",
			changeValue: "apples",
			expected:    "a = apples",
		},
		{
			name:        "update value without spaces",
			input:       "a=b#note",
			changeValue: "apples",
			expected:    "a=apples#note",
		},
		{
			name:      "update key with leading whitespace",
			input:     "  a = b",
			changeKey: "apples",
			expected:  "  apples = b",
		},
		{
			name:     "empty value",
			input:    "a =",
			expected: "a =",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			// make a field
			field := ini.FindField(tc.input)
			// update it
			if tc.changeKey != "" {
				field.Key = tc.changeKey
			}
			if tc.changeValue != "" {
				field.Value = tc.changeValue
			}
			// render and compare
			actual := field.String()
			if actual != tc.expected {
				t.Errorf("actual = %v, expected = %v", actual, tc.expected)
			}
		})
	}
}
