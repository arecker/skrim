.PHONY: all
all: test build

build:
	go build -o bin/skrim-golang .

.PHONY:
test:
	go test -v ./...

.PHONY: clean
clean:
	rm -rf bin/
