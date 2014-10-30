#include <stdint.h>
#include <libxml/xmlreader.h>

typedef struct fx_schema fx_schema;

struct element {
	uint8_t namespaceId;
	const xmlChar *localname;
};

struct fx_schema {
	int type;
	int start;
	const struct element *elements;
	const uint16_t *keys;
	const uint16_t *keys_offsets;
	const uint16_t *actions;
	const uint16_t *actions_offsets;
	const uint16_t *targets;
	uint16_t first_final;
	void (*do_actions)(int, const uint16_t*);
};

struct stack {
	const fx_schema *schema;
	int state;
	void *result;
};

fx_schema *lookupSubstitution(const xmlChar* name)
{
	return NULL;
}

int fx_parse_xml(xmlTextReaderPtr rd, const fx_schema *schema)
{
	int ret, i, trans;
	int fake_close = 0;
	xmlReaderTypes ev_type;
	uint8_t keys_len;
	const uint16_t *keys;
	fx_schema *schemaToInvoke;
	struct {
		struct stack ss[16];
		int sp;
	} stack;

	stack.sp = 0;
	stack.ss[stack.sp] = (struct stack){schema, schema->start, NULL};

read:
	if (fake_close) {
		fake_close = 0;
		ev_type = XML_READER_TYPE_END_ELEMENT;
	} else {
		if ((ret = xmlTextReaderRead(rd)) != 1) {
			/* error reading the next event, either EOF or I/O error */
			goto IO_error;
		}
		ev_type = xmlTextReaderNodeType(rd);
	}

dispatch:
	schema = stack.ss[stack.sp].schema;
	int *state = &(stack.ss[stack.sp].state);
	keys_len = schema->keys_offsets[*state + 1] - schema->keys_offsets[*state];
	keys     = schema->keys + schema->keys_offsets[*state];

	printf("State %d accepts:\n", *state);
	for (i=0; i < keys_len; i++) {
		const xmlChar *keyname = schema->elements[keys[i]].localname;
		printf("  %s -> %d,", keyname, schema->targets[keys - schema->keys + i]);
	}
	puts("\n");

	switch (ev_type) {
	case XML_READER_TYPE_ELEMENT: {
		/* an element name can match a known element,
		 * a member of a substitution group or a wildcard
		 */
		fake_close = xmlTextReaderIsEmptyElement(rd);
		const xmlChar *localname = xmlTextReaderConstLocalName(rd);
		printf("Element OPEN %s\n", localname);
		for (i=keys_len; i > 0; i--, keys++) {
			const xmlChar *keyname = schema->elements[*keys].localname;
			printf("  comparing with %s\n", keyname);
			switch (keyname[0]) {
			case '/':
				continue;
			case '*':
				// wildcard
				goto match;
				break;
			case '!':
				// substitution group
				if ((schemaToInvoke = lookupSubstitution(localname + 1)) != NULL)
					goto match;
				break;
			default:
				// normal element
				if (xmlStrcmp(localname, keyname) == 0)
					goto match;
			}
		}
		}
		goto error;

	case XML_READER_TYPE_END_ELEMENT:
		/* if element close is supported it is the first in the list
		 * and has ID=0
		 */
		printf("Element CLOSE %s\n", xmlTextReaderConstLocalName(rd));
		if (keys_len < 1 || *keys != 0)
			goto error;
		break;

	case XML_READER_TYPE_TEXT:
	case XML_READER_TYPE_CDATA:
		printf("Text: %s\n", xmlTextReaderConstValue(rd));

	default:
		/* any other event is unsupported and does nothing */
		goto read;
	}

match:
	/* found match, execute associated actions */
	trans = keys - schema->keys;
	printf("Executing actions for transition %d: ", trans);
/*	for(i=0; i < schema->actions_offsets[trans + 1] - schema->actions_offsets[trans]; i++)
		printf("%d, ", schema->actions[schema->actions_offsets[trans] + i]);
	puts("\n");
*/
	schema->do_actions(schema->actions_offsets[trans + 1] - schema->actions_offsets[trans],
                       schema->actions + schema->actions_offsets[trans]);
	*state = schema->targets[trans];
	printf("  go into state %d\n", *state);

	if (schemaToInvoke != NULL) {
		stack.ss[++stack.sp] = (struct stack){schemaToInvoke, schemaToInvoke->start, stack.ss[stack.sp].result};
		if (schemaToInvoke->type) {
			schemaToInvoke = NULL;
			goto dispatch;
		}
	}
	schemaToInvoke = NULL;
	goto read;

fsm_return:
	stack.sp--;
	goto read;

error:
	/* we need to check if it is a real error */
	if (*state >= schema->first_final && stack.sp > 0)
		goto fsm_return;

IO_error:
	/* definitive a fatal error ... */
	return !(ret == 0 && *state >= schema->first_final);
}

const uint16_t test_targets_offsets[] = {
0, 0, 1, 9, 15, 17, 19, 21, 22, 23, 25, 26, 29, 33, 41, 42, 44, 49, 53, 56, 58, 60, 61, 63, 66, 68, 70, 71, 72, 73, 75, 76, 77, 78, 79, 80, 81, 82, 84, 85, 86, 88, 91, 92, 94, 96, 97, 99, 101, 105, 106, 107, 109, 111, 113, 114, 115, 116, 118, 119, 120, 121, 122, 124, 125, 127, 127
};
const uint16_t test_targets[] = {
2, 65, 9, 3, 4, 5, 6, 7, 8, 13, 14, 15, 10, 11, 12, 16, 4, 17, 5, 18, 6, 19, 20, 21, 22, 23, 24, 26, 25, 28, 27, 29, 30, 65, 9, 3, 4, 5, 6, 7, 8, 31, 31, 32, 65, 5, 6, 7, 8, 65, 6, 7, 8, 65, 7, 8, 33, 19, 34, 20, 35, 35, 36, 13, 11, 12, 13, 12, 37, 25, 38, 39, 13, 40, 29, 41, 42, 14, 43, 44, 45, 21, 24, 25, 37, 40, 28, 29, 40, 46, 47, 48, 49, 43, 50, 44, 51, 52, 46, 39, 47, 13, 10, 11, 12, 53, 54, 13, 55, 40, 47, 65, 8, 65, 56, 57, 58, 57, 59, 60, 61, 62, 63, 62, 64, 45, 59
};
const uint16_t test_keys[] = {
15, 0, 12, 23, 24, 25, 26, 29, 32, 0, 1, 3, 13, 18, 22, 0, 5, 0, 5, 0, 5, 27, 30, 1, 3, 0, 0, 16, 17, 0, 16, 17, 21, 0, 12, 23, 24, 25, 26, 29, 32, 0, 0, 2, 0, 25, 26, 29, 32, 0, 26, 29, 32, 0, 29, 32, 0, 5, 0, 5, 0, 0, 2, 0, 18, 22, 0, 22, 0, 5, 15, 15, 0, 0, 5, 15, 4, 0, 28, 31, 4, 0, 0, 17, 0, 0, 0, 17, 0, 19, 20, 0, 0, 5, 0, 5, 0, 0, 5, 0, 5, 0, 14, 18, 22, 0, 0, 0, 11, 0, 20, 0, 32, 0, 10, 6, 0, 5, 9, 7, 0, 8, 0, 5, 0, 0, 9
};
const uint16_t test_actions_offsets[] = {
0, 0, 1, 3, 5, 7, 9, 11, 13, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 16, 17, 17, 17, 17, 17, 17, 17, 17, 17, 17, 17, 18, 20, 22, 24, 26, 28, 30, 32, 32, 32, 32, 33, 35, 37, 39, 41, 42, 44, 46, 48, 49, 51, 53, 53, 53, 53, 53, 53, 53, 53, 53, 53, 53, 53, 53, 53, 53, 53, 53, 53, 53, 53, 53, 53, 53, 55, 57, 57, 57, 57, 57, 57, 57, 57, 57, 57, 57, 57, 57, 57, 57, 57, 57, 57, 57, 57, 57, 57, 57, 57, 57, 57, 58, 59, 59, 59, 59, 59, 60, 62, 63, 63, 63, 63, 63, 63, 63, 63, 63, 63, 63, 63, 63, 63
};
const uint16_t test_actions[] = {
0, 0, 1, 0, 1, 0, 3, 0, 4, 0, 5, 0, 6, 0, 9, 7, 10, 2, 2, 1, 2, 1, 2, 3, 2, 4, 2, 5, 2, 6, 2, 9, 2, 2, 4, 2, 5, 2, 6, 2, 9, 2, 2, 5, 2, 6, 2, 9, 2, 2, 6, 2, 9, 2, 8, 2, 11, 2, 2, 2, 2, 9, 2
};

const struct element test_elements[] = {
{0, "/"},
{2, "OnlineResource"},
{2, "*"},
{2, "InlineContent"},
{2, "Format"},
{3, "!expression"},
{2, "LookupValue"},
{2, "Data"},
{2, "Value"},
{2, "MapItem"},
{2, "Recode"},
{2, "ColorReplacement"},
{2, "ExternalGraphic"},
{2, "WellKnownName"},
{2, "MarkIndex"},
{2, "Graphic"},
{2, "GraphicFill"},
{2, "SvgParameter"},
{2, "Fill"},
{2, "InitialGap"},
{2, "Gap"},
{2, "GraphicStroke"},
{2, "Stroke"},
{2, "Mark"},
{2, "Opacity"},
{2, "Size"},
{2, "Rotation"},
{2, "AnchorPointX"},
{2, "AnchorPointY"},
{2, "AnchorPoint"},
{2, "DisplacementX"},
{2, "DisplacementY"},
{2, "Displacement"}
};

enum test_actions {
alloc_Graphic = 0,
array_Graphic_Symbol = 1,
restoreContext = 2,
setContext_Graphic_Opacity = 3,
setContext_Graphic_Size = 4,
setContext_Graphic_Rotation = 5,
setContext_Graphic_AnchorPoint = 6,
setContext_AnchorPoint_X = 7,
setContext_AnchorPoint_Y = 8,
setContext_Graphic_Displacement = 9,
setContext_Displacement_X = 10,
setContext_Displacement_Y = 11,
};

void test_do_actions(int len, const uint16_t *actions)
{
	int i;
	for(i=0; i < len; i++)
		switch((enum test_actions)actions[i]) {
		case alloc_Graphic: printf("alloc_Graphic\n"); break;
		case array_Graphic_Symbol: printf("array_Graphic_Symbol\n"); break;
		case restoreContext: printf("restoreContext\n"); break;
		case setContext_Graphic_Opacity: printf("setContext_Graphic_Opacity\n"); break;
		case setContext_Graphic_Size: printf("setContext_Graphic_Size\n"); break;
		case setContext_Graphic_Rotation: printf("setContext_Graphic_Rotation\n"); break;
		case setContext_Graphic_AnchorPoint: printf("setContext_Graphic_AnchorPoint\n"); break;
		case setContext_AnchorPoint_X: printf("setContext_AnchorPoint_X\n"); break;
		case setContext_AnchorPoint_Y: printf("setContext_AnchorPoint_Y\n"); break;
		case setContext_Graphic_Displacement: printf("setContext_Graphic_Displacement\n"); break;
		case setContext_Displacement_X: printf("setContext_Displacement_X\n"); break;
		case setContext_Displacement_Y: printf("setContext_Displacement_Y\n"); break;
		default:
			printf("Action %d not implemented!!\n", actions[i]);
		}
}

const fx_schema testSchema = (fx_schema){
	0,
	1,
	test_elements,
	test_keys,
	test_targets_offsets,
	test_actions,
	test_actions_offsets,
	test_targets,
	64,
	test_do_actions
};

int
main(int argc, char **argv)
{
    xmlTextReaderPtr reader;
    if (argc != 2)
        return(1);

    LIBXML_TEST_VERSION

    reader = xmlReaderForFile(argv[1], NULL, 0);
    if (reader == NULL) {
        fprintf(stderr, "Unable to open %s\n", argv[1]);
        return (1);
    }

    if (fx_parse_xml(reader, &testSchema))
    	printf("Error parsing document\n");

    xmlCleanupParser();
    xmlMemoryDump();

    return(0);
}

