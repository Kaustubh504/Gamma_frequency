Network 0 {
Layer CONV {
Type: CONV
Dimensions { K: 64, C: 3, Y: 224, X: 224, R: 7, S: 7 }
Dataflow {
TemporalMap(200,200) Y';
TemporalMap(3,3) C;
SpatialMap(37,37) K;
TemporalMap(3,3) R;
TemporalMap(43,43) X';
TemporalMap(4,4) S;
Cluster(81,P);
TemporalMap(1,1) R;
TemporalMap(1,1) K;
TemporalMap(1,1) X';
TemporalMap(1,1) C;
SpatialMap(1,1) Y';
TemporalMap(1,1) S;
}
}
}