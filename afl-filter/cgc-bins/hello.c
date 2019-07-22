#include <libcgc.h>

#define STR0 "Hello World\n"
#define STR1 "Goodbye\n"


void main(){
	char buf[1024];
	int ret;
	size_t size;

	ret = receive(STDIN, buf, sizeof(buf) - 1, &size);
	if (ret!=0)
		_terminate(8);

	if (size == 0)
		_terminate(9);

	buf[size] = 0;

	if(buf[0] == 0x41 && buf[1] == 0x42){
		transmit(STDOUT, STR0, sizeof(STR0) - 1, NULL);
	}
	else{
		transmit(STDOUT, STR1, sizeof(STR1) - 1, NULL);
	}

}