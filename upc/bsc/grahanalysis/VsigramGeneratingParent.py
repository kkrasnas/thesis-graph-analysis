import datetime
from pynauty import *
import networkx as nx
import csv
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

from upc.bsc.grahanalysis.VsigramGraph import VsigramGraph


def map_csv_to_graph(path='/home/kkrasnas/Documents/thesis/pattern_mining/validation_data/new_assignment_separate.csv'):
    with open(path, 'rb') as csvfile:
        reader = csv.DictReader(csvfile, fieldnames=['pos_1', 'pos_2'])
        next(csvfile)
        positions = list()
        edges_set = set()
        edges = list()
        for row in reader:
            positions.append((row['pos_1'], row['pos_2']))

        vertices_set = set()
        for position in positions:
            vertices_set.add(position[0])
            vertices_set.add(position[1])
        vertices_list = list(vertices_set)
        g = Graph(len(vertices_list))

        # ORIGINAL EDGES ARE ALL SORTED MIN -> MAX
        for edge in positions:
            # always minIndex -> maxIndex to avoid duplicate edges
            if vertices_list.index(edge[0]) < vertices_list.index(edge[1]):
                g.connect_vertex(vertices_list.index(edge[0]), vertices_list.index(edge[1]))
                edges_set.add((vertices_list.index(edge[0]), vertices_list.index(edge[1])))
            else:
                g.connect_vertex(vertices_list.index(edge[1]), vertices_list.index(edge[0]))
                edges_set.add((vertices_list.index(edge[1]), vertices_list.index(edge[0])))
        edges = list(edges_set)
        return VsigramGraph(g, get_subgraph_hash(edges), certificate(g), canon_label(g), 1, 1,
                            edges=edges, vertices=range(len(vertices_list)),
                            orig_edges=positions, orig_vertices=vertices_list)


def get_subgraph_hash(edges):
    # ORDER INSIDE EDGES IS ALREADY DONE
    # NOW ONLY NEED TO ORDER EDGES BETWEEN THEMSELVES
    hash_str = ''
    # rearrange the edges
    edges = sorted(edges)  # sorts on the first elements first and then on second
    for edge in edges:
        hash_str += str(edge[0]) + '.' + str(edge[1]) + ';'
    return hash_str


def vsigram(G, min_freq, max_size):
    MCLf = dict()
    MCLf1 = dict()
    for edge in G.edges:
        # ceate new graph - subgraph of
        vertices = set(edge)
        g = Graph(len(vertices))
        vertices_list = list(vertices)
        g.connect_vertex(vertices_list.index(edge[0]), vertices_list.index(edge[1]))
        edges_list = list()
        edges_list.append((vertices_list.index(edge[0]), vertices_list.index(edge[1])))
        #aut = autgrp(g)
        #print label.decode('utf-8')
        subgraph1 = VsigramGraph(g, get_subgraph_hash([edge]), label=certificate(g), label_arr=canon_label(g),
                                 edges=edges_list, vertices=range(len(vertices_list)),
                                 orig_edges=[edge], orig_vertices=vertices_list)
        if subgraph1.label_arr not in MCLf1:
            MCLf1[subgraph1.label_arr] = [subgraph1]
        else:
            MCLf1[subgraph1.label_arr].append(subgraph1)

    # for each clf1 in CLf1 do
    for key in MCLf1.keys():
        # M(clf1) =  all subgraphs with canonical label clf1
        # remove an element from dictionary if number of subgraphs < minFreq
        if len(MCLf1[key]) < min_freq:
            #remove from frequent labels and frequent subgraphs
            del MCLf1[key]
        else:
            # add to all frequent
            MCLf[key] = MCLf1[key]

    # end for

    # for each clf1 in CLf1 do
    for clf1 in MCLf1.keys():
        # CLf = CLf + vsigram_exten(clf1, G, minFreq)
        MCLf.update(vsigram_extend(clf1, MCLf1[clf1], G, min_freq, MCLf, 1 + 1, max_size))
    # end for
    # FINALLY CHECK ALL FREQUENCIES
    # print 'Starting to eliminate keys'
    # for key in MCLf.keys():
    #     if len(MCLf[key]) < minFreq:
    #         del MCLf[key]
    # # return MCLf
    return MCLf


def generating_parent(c_child, c_parent):
    # find all edges of the child
    # '  0:  0;  1:  6 7;  2:  2 8;  3:  3 13;  4:  4 12;  5:  5 9 13;  6:  1 6 11;  7:  1 7 14;  8:  2 8 9;  9:  5 8 10 14; 10:  9 12 14 15; 11:  6 11 13 15; 12:  4 10 12 15; 13:  3 5 11 13; 14:  7 9 10 14 15; 15:  10 11 12 14 15;'
    edges = list()
    adj_elements = c_child[:-1].split(';')
    for adj_line in adj_elements:
        adj_line = adj_line.strip()
        edges_line = adj_line.split(':')
        out_edge = int(edges_line[0])
        in_edges = edges_line[1].strip().split(' ')
        for element in in_edges:
            in_edge = int(element)
            if (out_edge < in_edge) and ((out_edge, in_edge) not in edges):
                edges.append((out_edge, in_edge))
            else:
                if (in_edge, out_edge) not in edges:
                    edges.append((in_edge, out_edge))

    # deleting last edge
    orig_edges = list(edges)
    last_index = len(edges) - 1
    last_edge = orig_edges[last_index]
    while last_edge is not None:
        edges = list(orig_edges)
        edges.remove(last_edge)
        # create networkx graph
        nx_g = nx.Graph()
        nx_g.add_edges_from(edges)
        if not nx.is_connected(nx_g):
            print 'Graph is not connected'
            last_index -= 1
            print 'Last index is ' + str(last_index)
            last_edge = orig_edges[last_index]
        else:
            last_edge = None
    # found good graph, now create the pynauty version
    vertices = set()
    for edge in edges:
        vertices.add(edge[0])
        vertices.add(edge[1])
    vertices_list = list(vertices)
    g = Graph(len(vertices_list))
    for edge in edges:
        g.connect_vertex(vertices_list.index(edge[0]), vertices_list.index(edge[1]))
    label = canon_label(g)
    return label == c_parent


def vsigram_extend(clfk, Mclfk, G, minFreq, MCLf, size, max_size):
    if size > max_size:
        return MCLf
    #print 'Processing size ' + str(size)
    # Sk+1 = NULL
    Skplus1 = set()
    # CLk+1 = NULL  // stores new, distinct canonical labels
    MCLkplus1 = dict()
    # for each sk in M(clfk ) do
    for sk in Mclfk:
        # Sk+1 = Sk+1 + {sk + e | e from E} // extend subgraph with an edge
        for orig_edge in G.edges:
            # check if edge is adjacent
            if (orig_edge not in sk.orig_edges) \
                    and (orig_edge[0] in sk.orig_vertices or orig_edge[1] in sk.orig_vertices):
                # create new graph
                # new set of vertices
                orig_vertices = set(sk.orig_vertices)
                # add each vertex of the new edge (max one of them is added)
                orig_vertices.add(orig_edge[0])
                orig_vertices.add(orig_edge[1])
                orig_vertices_list = list(orig_vertices)
                # new list of edges from original edges
                orig_edges = list(sk.orig_edges)
                # add new edge
                orig_edges.append(orig_edge)
                g = Graph(len(orig_vertices))
                edges = list()
                for new_orig_edge in orig_edges:
                    g.connect_vertex(orig_vertices_list.index(new_orig_edge[0]), orig_vertices_list.index(new_orig_edge[1]))
                    edges.append((orig_vertices_list.index(new_orig_edge[0]), orig_vertices_list.index(new_orig_edge[1])))
                subgraphkplus1 = VsigramGraph(g, get_subgraph_hash(orig_edges), certificate(g), canon_label(g),
                                              edges=edges, vertices=range(len(orig_vertices_list)),
                                              orig_edges=orig_edges, orig_vertices=orig_vertices_list)
                Skplus1.add(subgraphkplus1)
    # end for
    # for each sk+1 in Sk+1
    # ON THIS LEVEL CHECK IF THE SUBGRAPH HAS ALREADY BEEN PROCESSED AND DO NOT ADD IT IN THIS CASE!
    for skplus1 in Skplus1:
        # CLk+1 = CLk+1 + (sk+1.label) // only distinct canonical labels
        # M(sk+1.label) = M(sk+1.label) + {sk+1} //add subgraph
        if skplus1.label_arr not in MCLkplus1:
            MCLkplus1[skplus1.label_arr] = [skplus1]
        else:
            MCLkplus1[skplus1.label_arr].append(skplus1)
    # end for
    # for each clk+1 in CLk+1 do
    for clkplus1 in MCLkplus1.keys():
        # if clfk is not the generating parent of clk+1 then
        # print 'frequency of ' + clkplus1 + ' is ' + str(len(MCLkplus1[clkplus1]))
        if not generating_parent(clkplus1, clfk):  # generating parent function
            # print 'size: ' + str(size) + ', ' + clkplus1 + ' is NOT a child of ' + clfk
            continue
        # end if
        # print 'size: ' + str(size) + ', ' + clkplus1 + ' is a child of ' + clfk
        # compute clk+1.freq from M(clk+1)
        # if clk+1.freq < minFreq then

        if len(MCLkplus1[clkplus1]) < minFreq:
            continue
        # end if
        # CLf = CLf + {clk+1} + vsigram_extend(clk+1, G, minFreq)
        if clkplus1 not in MCLf:
            MCLf[clkplus1] = MCLkplus1[clkplus1]
        else:
            MCLf[clkplus1].append(MCLkplus1[clkplus1])
        MCLf.update(vsigram_extend(clkplus1, MCLkplus1[clkplus1], G, minFreq, MCLf, size+1, max_size))
    # end for
    # print 'Done with size ' + str(size)
    return MCLf

sizes = [1, 2, 3, 4]
milliseconds_per_size = []
milliseconds = []
for i in sizes:
    start_time = datetime.datetime.now()
    print 'Start time is:' + str(start_time)
    graph = map_csv_to_graph()
    frequent_subgraphs = vsigram(graph, 1, i)
    end_time = datetime.datetime.now()
    elapsed = end_time - start_time
    print 'End time is:' + str(end_time)

    print 'Elapsed: ' + str(elapsed) + ' ' + str(elapsed.total_seconds() * 1000)
    milisec = elapsed.total_seconds() * 1000

    milliseconds_per_size.append(milisec - milliseconds[len(milliseconds) - 1] if len(milliseconds) > 0 else 0)
    milliseconds.append(milisec)
    #print len(frequent_subgraphs)

    for pattern in frequent_subgraphs.keys():
        print pattern + ': ' + str(len(frequent_subgraphs[pattern])) + ', edges: ' + str(len(frequent_subgraphs[pattern][0].edges))

print milliseconds
print milliseconds_per_size
 # create plot
# plt.yscale('log')
ax = plt.figure().gca()
ax.xaxis.set_major_locator(MaxNLocator(integer=True))
ax.plot(sizes, milliseconds_per_size, 'bD', sizes, milliseconds_per_size, 'b')
ax.xaxis.set_label_text('Size of patterns')
ax.yaxis.set_label_text('Time (ms)')
##ax.xlabel('Size of patterns')
##ax.ylabel('Time (ms)')
plt.show()

