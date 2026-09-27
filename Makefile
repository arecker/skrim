.PHONY: all
all: bin/skrim

bin/skrim: main.go go.mod
	go build -o bin/skrim-golang .

.PHONY: clean
clean:
	rm -rf bin/
