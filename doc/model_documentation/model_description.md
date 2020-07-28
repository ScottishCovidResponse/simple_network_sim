# Simple network simulation - model description



## Overview
**S**imple **n**etwork **s**im (sns) is network-based simulation model built for COVID-19 and written in Python.

Each node in an edge-weighted network contains an age-structured population and fractional people within that population are recorded as in various disease states. We assume that the temporal scale of the simulation is such that individuals do not progress between age classes, nor are any new individuals introduced. These nodes might be used to model e.g. health boards, counties, or datazones.  

After seeding disease at specified nodes, sns simulates progression of an outbreak due to both within- and between-node infectious contacts.  Infection and disease progression can be run either deterministically (resulting in fractional people in each disease state) or stochastically.  The end result of the model is a timeseries of the number of people in each
node, compartment and age.

## Inputs

Data, parameters, and the compartmental model to be used are all passed to sns as inputs and accessed via the SCRC Data Pipeline API.  

#### Disease-specific
- compartmental model
- infectious classes
- transition rates
- infection probability of a contact

#### Network characteristics
- weighted edges


#### Within-node information
- age-structured population at nodes
- mixing between age classes at nodes

#### Time varying-modifiers
- movement modifiers
- contact rate modifiers

## Algorithm of simulation
Simple network sim uses a notionally daily timestep, and forward-simulates by performing local and between-region infection followed by disease progression updating based on rates supplied as part of the compartmental model.

### Central infection mechanism: infectious contacts 
The central mechanism of infection uses the notion of a number of infectious contacts that are distributed amongst the population in a node, structured by age class.  A single infectious contact allocated to a node is a contact that is between a person in an infectious class either within the node or from another node and a person who is susceptible within the node.  We take the total number of all of the infectious contacts (both due to within and between node infection) that exert infectious pressure at a time step, and then using that total number distribute the infectious contacts to a number of target individuals within the node using either a fixed combinatorial expression or a hypergeometric distribution to draw (with replacement) the number of susceptible people who are subject to those infectious contacts, subject to a specified probability of transmission given a single infectious contact.  This takes account of the possiblity of a single susceptible individual in a node being the recipient of multiple infectious contacts.  

#### Calculating the number of within-node infectious contacts
The number of infectious contacts targetting susceptible individuals in age class $A_i$ is a function of the proportion of infectious individuals in each age class within the node and the expected number of contacts between an individual in $A_i$ and individuals in each of the source age classes. For a single source age class $A_j$ where $C_{i,j}$ is the number of contacts that an individual in $A_i$ expects to have with individuals in $A_j$, and $N(A_k)$, $S(A_k)$, $I(A_k)$ are the number of all, susceptible, and infectious-class (respectively) individuals in age class $A_k$ at the previous time, then the number of within-node infectious contacts from $A_j$ to $A_i$ in the deterministic model is: 
$$
C_{i,j}\frac{I(A_j)}{N(A_j)}\frac{S(A_i)}{N(A_i)}
$$

#### Calculating the number of between-node infectious contacts
For between-node infectious contact calculations, we use an input file of expected directional contacts, an optional time-varying movement modifier, and the disease state at the previous time of the nodes involved.  For a particular pair of nodes $u, v$, let $w(u, v)$ be the number of expected directional contacts, $x$ the appropriate time's movement modifier, $p_{v,I}$ the proportion of .  

# Notation
- $w(u, v)$ is the number of expected contacts from node $u$ to node $v$, supplied as part of an input file
- $x_t$ is the (optional) movement modifier at time $t$, supplied as part of an input file
- $y_t$ is the (optional) contact modifier at time $t$, supplied as part of an input file
- $A_{u,k}$ is age class $k$ at node $u$
    - Where it is clear that we are talking about individuals in all nodes we may abuse notation and use $A_k$
- $X_t(A_{u,k})$ where $X$ is a compartment in the compartmental model is the number of individuals in compartment $X$ in age class $A_k$ in node $u$ at time $t$
- For convenience, we also define $\mathcal{I}_t(A_{u,k})$ as the number of individuals in **any** infectious compartment in age class $A_k$ in node $u$ at time $t$
- $C$ is a matrix describing contact between age classes, where $C_{i,j}$ is the expected number of contacts that an individual in age class $A_i$ has with an individual in age class $A_j$.
- 


### Infection Seeding

### Disease progression

### Within- and between-node infection