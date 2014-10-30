#!/usr/bin/python
# encoding=UTF-8

from collections import deque
import libxml2, sys, os, re
import urlparse, argparse
sys.path.append(".")
sys.setrecursionlimit(10000)
from fsm import XMLFsm, State

class switch(object):
	def __init__(self, value):
		self.value = value
		self.fall = False

	def __iter__(self):
		yield self.match
		raise StopIteration

	def match(self, *args):
		if self.fall or not args:
			return True
		elif self.value in args:
			self.fall = True
			return True
		else:
			return False

class XSCompiler:
	XSC_NS = "urn:application:xsc"
	def __init__(self):
		self.genElements = set()
		self.genTypes = set()
		self.providedElements = set()
		self.providedTypes = set()
		self.preservedSubsts = set()
		self.substs = dict()
		self.Decls = {0: dict(), 1: dict(), 2: dict()}
		self.declTypes = dict(attribute=0, element=1, complexType=2, attributeGroup=0, group=1, simpleType=2)
		self.loadedSchemas = set()
		self.definitions = dict()
		self.namespaces = list()
		for namespace in ("http://www.w3.org/2001/XMLSchema", "http://www.w3.org/2001/XMLSchema-datatypes"):
			for typename in ("anyType", "anySimpleType", "duration", "dateTime", "time", "date", "gYearMonth",
			                 "gYear", "gMonthDay", "gDay", "gMonth", "boolean", "base64Binary", "hexBinary",
			                 "float", "double", "anyURI", "QName", "NOTATION", "decimal", "integer",
			                 "nonPositiveInteger", "negativeInteger", "long", "int", "short", "byte",
			                 "nonNegativeInteger", "positiveInteger", "unsignedLong", "unsignedInt", "unsignedShort",
			                 "unsignedByte", "string", "normalizedString", "token", "language", "Name", "NCName",
			                 "ID", "IDREF", "IDREFS", "ENTITY", "ENTITIES", "NMTOKEN", "NMTOKENS"):
				self.Decls[2]["{%s}%s" % (namespace, typename)] = None
			self.namespaces.append(namespace)
		self.elements = [("/")]
		self.actions = []
		self.macros = [ ("enter", 0, self.onEnter), ("leave", 0, self.onLeave) ]

	def expandQName(self, node, qname, defaultNamespace=""):
		try:
			prefix, localname = qname.split(":")
		except ValueError:
			localname = qname
			prefix = None
		try:
			retval = "{%s}%s" % (node.searchNs(node.get_doc(), prefix).content, localname)
		except libxml2.treeError:
			retval = "{%s}%s" % (defaultNamespace, localname)
		return retval

	def importDef(self, node, targetNamespace):
		declNames = ("attribute", "element", "type")
		qname = "{%s}%s" % (targetNamespace, node.prop("name"))
		self.Decls[self.declTypes[node.name]][qname] = node
		print "Registered %s %s" % (declNames[self.declTypes[node.name]], qname)
		subst = node.prop("substitutionGroup")
		if bool(subst):
			subst = self.expandQName(node, subst)
			if not self.substs.has_key(subst): self.substs[subst] = set()
			self.substs[subst].add(node)
			print "  added %s as substitut for %s" % (qname, subst)

	def loadSchema(self, uri, targetNamespace = None):
		if uri in self.loadedSchemas: return
		print "Loading schema file: %s" % uri
		self.loadedSchemas.add(uri)

		doc = libxml2.readFile(uri, None, options = libxml2.XML_PARSE_NOBLANKS)
		root = doc.getRootElement()
		xpath = doc.xpathNewContext()

		if targetNamespace is None:
			targetNamespace = root.prop("targetNamespace")

		result = xpath.xpathEval("/*[local-name()='schema']/*[local-name()='include' or local-name()='import']")
		for node in result:
			url = urlparse.urlparse(node.prop("schemaLocation"))
			if bool(url.scheme):
				print "  Ignoring non-local resource %s" % node.prop("schemaLocation")
			else:
				loc = os.path.normpath(os.path.join(os.path.dirname(uri), url.path))
				self.loadSchema(loc, targetNamespace if node.name == "include" else None)

		result = xpath.xpathEval("/*[local-name()='schema']/*")
		for node in result:
			if node.name in self.declTypes:
				self.importDef(node, targetNamespace)

	def targetNamespace(self, node):
		return node.get_doc().getRootElement().prop("targetNamespace")

	def getElementId(self, namespace, localname):
		try:
			namespaceId = self.namespaces.index(namespace)
		except ValueError:
			namespaceId = len(self.namespaces)
			self.namespaces.append(namespace)

		element = (namespaceId, localname)
		try:
			elementId = self.elements.index(element)
		except ValueError:
			elementId = len(self.elements)
			self.elements.append(element)
		return elementId
	
	def getActionId(self, action):
		try:
			actionId = self.actions.index(action)
		except ValueError:
			actionId = len(self.actions)
			self.actions.append(action)
		return actionId

	def mapActions(self, actionStrings):
		return map(self.getActionId, actionStrings)
		
	def getActions(self, s):
		if s is None: return []
		l = []
		for i in re.finditer(r"\s*(\w+)\s*\(\s*((\w+\s*(,\s*\w+)*)?\s*)\)", s):
			args = "_".join([a.group(1).replace("_", "__") for a in re.finditer(r",?\s*(\w+)", i.group(2))])
			action = "%s%s%s" % (i.group(1).replace("_", "__"), "_" if len(args) > 0 else "", args)
			actionId = self.getActionId(action)
			l.append(actionId)
#		print "Action IN: %s | OUT: %s" % (s, l)
		return l

	@staticmethod
	def onEnter(self, action, ea, la):
		l = self.getActions(action)
		ea.extend(l)

	@staticmethod
	def onLeave(self, action, ea, la):
		l = self.getActions(action)
		la[:0] = l

	def addMacro(self, macro):
		for i in range(0, len(self.macros)):
			if self.macros[i][1] >= macro[1]: break
		print "Inserting macro %s with prio %d at %d" % (macro[0], macro[1], i)
		self.macros[i:i] = [macro]
		print self.macros

	def processActions(self, node, ea, la):
		for macro in self.macros:
			action = node.prop(macro[0])
			if not action:
				continue
			macro[2](self, action, ea, la)

	def mkTables(self, dfa):
		keys = []
		targets = []
		targets_offsets = [0]
		Lactions = []
		Lactions_offsets = []
		
		states = sorted(dfa.reachables(), key=lambda state: state in dfa.accepts)
		for i in range(0, len(states)):
			labels = sorted(set([trans.label for trans in states[i].transitions]))
			targets_offsets.append(len(targets))
			for label in labels:
				target, actions = [(states.index(trans.target), trans.actions) for trans in states[i].transitions if trans.label == label][0]
				targets.append(target + 1)
				Lactions_offsets.append(len(Lactions))
				Lactions.extend(actions)
				keys.append(label)
				print "State %d, label %s, target %d, actions %s" % (i, label, target, actions)
		targets_offsets.append(len(targets))
		Lactions_offsets.append(len(Lactions))
		print "Targets_offsets: %s" % targets_offsets
		print "Targets: %s" % targets
		print "Keys: %s" % keys
		print "Actions: %s" % Lactions
		print "Actions_offsets: %s" % Lactions_offsets
		print "{0, \"/\"},"
		for i in range(1, len(self.elements)):
			print "{%d, \"%s\"}," % (self.elements[i][0], self.elements[i][1])
		for idx, action in enumerate(self.actions):
			print "%s = %d," % (action, idx)

	def dump(self, nfa):
		states = sorted(nfa.reachables(), key=lambda state: state in nfa.accepts)
		for i in range(0, len(states)):
			labels = set([trans.label for trans in states[i].transitions])
			tr = []
			for label in labels:
				targets = [trans.target for trans in states[i].transitions if trans.label == label]
				targetStr = []
				for target in targets:
					actions = []
					for list in [trans.actions for trans in states[i].transitions if trans.label == label and trans.target == target]:
						actions.extend(list)
					targetStr.append("%s / %s" % (states.index(target), ", ".join([self.actions[a] for a in actions])))
				tr.append("%s -> %s" % ("€" if label is None else self.elements[label], ", ".join(targetStr)))
			transStr = ", ".join(tr)
			line = "%s\t%s%d%s: %s" % ("entry" if states[i] == nfa.entry else "", "[" if states[i] in nfa.accepts else " ", i, "]" if states[i] in nfa.accepts else " ", transStr)
			print line

	def createContentModel(self, node, _stack = list()):
		name = node.prop("name")
		minOccurs = node.prop("minOccurs")
		minOccurs = 1 if minOccurs is None else int(minOccurs)
		maxOccurs = node.prop("maxOccurs")
		maxOccurs = 1 if maxOccurs is None else (maxOccurs if maxOccurs == "unbounded" else int(maxOccurs))
		fsm = None
		ea = list()
		la = list()
		self.processActions(node, ea, la)
		if _stack.count(node) > 0:
			if node.name != "element" or ("{%s}%s" % (self.targetNamespace(node), name)) not in self.providedElements:
				print "*** recursion detected ***"
				return XMLFsm().empty()

		stack = list(_stack)
		stack.append(node)
		print "%s%s: '{%s}%s' (%s, %s) %s | %s" % (len(_stack)* "  ", node.name, self.targetNamespace(node), name, minOccurs, maxOccurs, [self.actions[e] for e in ea], [self.actions[a] for a in la])
		for case in switch(node.name):
			if case("element"):
				# wenn Referenz, dann verwende das Model des referenzierten Elements und wende Aktionen und Particle-Rule an
				if node.prop("ref") is not None:
					ref = self.Decls[1][self.expandQName(node, node.prop("ref"))]
					if ref is None:
						raise BaseException("Referenced element not known: %s" % node.prop("ref"))
#					print "Verwende referenz %s" % node.prop("ref")
					fsm = self.createContentModel(ref, stack).onenter(ea).onleave(la).particle(minOccurs, maxOccurs)
				else:
				# sonst, falls nicht abstract, baue das Modell aus dem angegebenen Typ oder den Kind-Elementen
				#   und erzeuge das Element
				# erzeuge für jedes Mitglied der SubstitutionGroup das Inhaltsmodell und ggf. den Aufruf für die Gruppe
				#   und füge diese mit dem für dieses Element zusammen
				# Ist das Element provided, wird ein Einsprung dafür definiert
					substitutions = []
					name = node.prop("name")
					if name is None:
						raise BaseException("Element declaration requires a name")
					
					qname = "{%s}%s" % (self.targetNamespace(node), name)
					if qname in self.providedElements or \
					   qname in self.elements:
#						print "Creating call to %s" % name
						# Einsprung via Element-Name in Zielmaschine; abstract="true" impliziert --preserve-substitution
						fsm = XMLFsm()
						fsm.entry = State()
						leave = State()
						fsm.entry.addTransition(self.getElementId(self.targetNamespace(node), "%s%s" % ('!' if node.prop("abstract") == "true" else "", name)), leave, ea)
						fsm.accepts.add(leave)
						fsm = fsm.particle(minOccurs, maxOccurs)
					else:
#						print "%s nicht in %s" % (qname, self.providedElements)
						if "{%s}%s" % (self.targetNamespace(node), name) in self.genElements:
							self.providedElements.add("{%s}%s" % (self.targetNamespace(node), name))
						if node.prop("abstract") != "true":
#							print "Erzeuge content model fuer %s" % name
							content = None
							# compute the direct content model
							if node.prop("type") is not None:
								typename = self.expandQName(node, node.prop("type"), self.targetNamespace(node))
								if not self.Decls[2].has_key(typename):
									raise BaseException("Unknown type %s" % typename)
								if self.Decls[2][typename] is not None:
									content = self.createContentModel(self.Decls[2][typename], stack)
								# if None, it is a predefined simpleType
							else:
								child = node.children
								while child is not None:
									if child.name in ("simpleType", "complexType"):
										content = self.createContentModel(child, stack)
										break
									child = child.next
							if content is None:
								content = XMLFsm().empty()
							substitutions.append(XMLFsm().element(self.getElementId(self.targetNamespace(node), name), content, ea, la).particle(minOccurs, maxOccurs))
#						else:
#							print "Kein content-model fuer %s, da abstract" % name

						if self.substs.has_key(qname):
							for child in self.substs[qname]:
#								print "Fuege subst %s fuer %s hinzu" % (child.prop("name"), qname)
								substitutions.append(self.createContentModel(child, stack))
						if qname in self.preservedSubsts:
							f = XMLFsm()
							f.entry = State()
							leave = State()
							f.entry.addTransition(self.getElementId(self.targetNamespace(node), "!%s" % name), leave, ea)
							f.accepts.add(leave)
							substitutions.append(f)
						fsm = XMLFsm().empty() if len(substitutions) == 0 else XMLFsm().choice(substitutions).particle(minOccurs, maxOccurs)
				break

			if case("simpleType", "simpleContent"):
				fsm = XMLFsm().empty()
				break

			if case("complexType"):
				if node.prop("name") is None or self.expandQName(node, node.prop("name"), self.targetNamespace(node)) not in self.providedTypes:
					if "{%s}%s" % (self.targetNamespace(node), name) in self.genTypes:
						self.providedTypes.add("{%s}%s" % (self.targetNamespace(node), name))
					child = node.children
					while child is not None:
						if child.name in ("simpleContent", "complexContent", "group", "choice", "sequence", "all"):
							fsm = self.createContentModel(child, stack).onenter(ea).onleave(la)
							break
						child = child.next
				if fsm is None: fsm = XMLFsm().empty()
				break

			if case("sequence", "choice"):
				content = []
				child = node.children
				while child is not None:
					if child.name in ("element", "group", "choice", "sequence", "any"):
						content.append(self.createContentModel(child, stack))
					child = child.next
				fsm = XMLFsm().empty() if len(content) == 0 else (
					XMLFsm().sequence(content, ea, la) if node.name == "sequence" else
					XMLFsm().choice(content, ea, la)
					).particle(minOccurs, maxOccurs)
				break

			if case("complexContent"):
				content = None
				child = node.children
				while child is not None:
					if child.name in ("extension", "restriction"):
						content = self.createContentModel(child, stack)
						break
					child = child.next
				fsm = XMLFsm().empty() if content is None else content
				break

			if case("extension", "restriction"):
				if node.name == "extension":
					qname = self.expandQName(node, node.prop("base"), self.targetNamespace(node))
					if qname not in self.Decls[2]:
						raise BaseException("base type %s not known" % qname)
					base = self.Decls[2][qname]
					baseContent = XMLFsm().empty() if base is None else self.createContentModel(base, stack)
				else:
					baseContent = XMLFsm().empty()
				content = None
				child = node.children
				while child is not None:
					if child.name in ("group", "choice", "sequence"):
						content = self.createContentModel(child, stack)
						break
					child = child.next
				fsm = baseContent if content is None else baseContent.concat(content)
				break

			if case("any"):
				fsm = XMLFsm().element(self.getElementId(self.targetNamespace(node), "*"), XMLFsm().empty(), ea, la).particle(minOccurs, maxOccurs)
				break

			if case("group"):
				if node.prop("ref") is not None:
					ref = self.Decls[1][self.expandQName(node, node.prop("ref"))]
					if ref is None:
						raise BaseException("Referenced group not known: %s" % node.prop("ref"))
					fsm = self.createContentModel(ref, stack).onenter(ea).onleave(la).particle(minOccurs, maxOccurs)
				else:
					content = None
					child = node.children
					while child is not None:
						if child.name in ("all", "choice", "sequence"):
							content = self.createContentModel(child, stack)
							break
						child = child.next
					fsm = XMLFsm().empty if content is None else content.onenter(ea).onleave(la)
				break

			if case():
				raise BaseException("Unknown schema object: %s" % node.name)
#		self.dump(fsm)
#		print "*" * 32
		if len(stack) % 5 == 0: fsm = fsm.determinize(False).minimize(False)
		return fsm

class myArgumentParser(argparse.ArgumentParser):
	def __init__(self, **kwargs):
		super(myArgumentParser, self).__init__(**kwargs)

	def convert_arg_line_to_args(self, arg_line):
		args = arg_line.split("=", 1)
		yield "--" + args[0].strip()
		yield args[1].strip()

if __name__ == "__main__":
	parser = myArgumentParser(description="Turn XML schema objects into finite state machines", fromfile_prefix_chars="@")
	parser.add_argument("-v", "--verbose", action="count", default="0", dest="verbosity",
	                    help="increase output verbosity")
	parser.add_argument("--element", action="append", dest="elements", default=[],
	                    help="element name to create machine for")
	parser.add_argument("--types", action="append", dest="types", default=[],
	                    help="type name to create machine for")
	parser.add_argument("--provide-element", action="append", dest="elementsProvided", default=[],
	                    help="element name that will be provided by other means")
	parser.add_argument("--provide-type", action="append", dest="typesProvided", default=[],
	                    help="type name that will be provided by other means")
	parser.add_argument("--preserve-substitution", action="append", dest="preservedSubsts", default=[],
	                    help="type name that will be provided by other means")
	parser.add_argument("--schema", action="append", dest="schemaFiles", default=[],
                        help="XML schema file to import definitions from")
	arguments = parser.parse_args()
	#print arguments

	cc = XSCompiler()
	cc.preservedSubsts = arguments.preservedSubsts

	for file in arguments.schemaFiles:
		try:
			cc.loadSchema(os.path.normpath(file))
		except libxml2.treeError as e:
			print "Unable to load schema file '{0}': {1}".format(file, e)
			sys.exit(1)

	cc.genTypes = set(arguments.types)
	cc.providedTypes = set(arguments.typesProvided).union(arguments.types)
	for obj in arguments.elements:
		cc.genElements = set([obj])
		cc.providedElements = set(arguments.elementsProvided).union(arguments.elements) - set([obj])
		nfa = cc.createContentModel(cc.Decls[1][obj])
		dfa = nfa.determinize().minimize()
		cc.dump(dfa)
		cc.mkTables(dfa)
#		dfa = nfa.determinize().hopcroft()
#		cc.dump(dfa)

	cc.genElements = set(arguments.elements)
	cc.providedElements = set(arguments.elementsProvided).union(arguments.elements)
	for obj in arguments.types:
		cc.genTypes = set([obj])
		cc.providedTypes = set(arguments.typesProvided).union(arguments.types) - set([obj])
		nfa = cc.createContentModel(cc.Decls[2][obj])
		dfa = nfa.determinize().minimize()
		cc.dump(dfa)
