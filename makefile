.PHONY: run install

run: install
	./hypotenuse $(ARGS)

install:
	cmake -S . -B cmake-build-debug
	cmake --build cmake-build-debug
	cp cmake-build-debug/C_Triangle hypotenuse
