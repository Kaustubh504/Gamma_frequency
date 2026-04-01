Network 0 {
Layer CONV {
Type: CONV
Dimensions { K: 64, C: 3, Y: 224, X: 224, R: 7, S: 7 }
Dataflow {
TemporalMap(5,5) S;
TemporalMap(4,4) R;
SpatialMap(9,9) K;
TemporalMap(200,200) Y';
TemporalMap(2,2) C;
TemporalMap(43,43) X';
Cluster(133,P);
TemporalMap(9,9) K;
TemporalMap(1,1) X';
TemporalMap(1,1) C;
TemporalMap(4,4) S;
SpatialMap(1,1) Y';
TemporalMap(1,1) R;
}
}
}