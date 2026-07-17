# In-tree FreeSWITCH build wiring for the vendored mod_audio_fork.
#
# FreeSWITCH's in-tree module build (build/modmake.rules) compiles only
# $(MODNAME).c and ignores the upstream Makefile.am, so mod_audio_fork's extra
# C++ sources and external libraries are declared here through modmake.rules'
# LOCAL_* variables. modmake.rules only auto-generates a stub Makefile when one
# does not already exist (`test ! -f`), so this file is honored as-is.
BASE=../../../..

# LOCAL_OBJS are extra object files linked into the module; modmake.rules
# builds them from the matching .cpp via its .cpp.o suffix rule.
LOCAL_CFLAGS=$(shell pkg-config --cflags libwebsockets)
LOCAL_OBJS=lws_glue.o parser.o audio_pipe.o vector_math.o
# Link flags go in LOCAL_LDFLAGS_POST (appended after the objects, and NOT part
# of the target's prerequisite list, unlike LOCAL_LIBADD).
LOCAL_LDFLAGS_POST=$(shell pkg-config --libs libwebsockets) -lstdc++ -lboost_system -lboost_thread

include $(BASE)/build/modmake.rules
