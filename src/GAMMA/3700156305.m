Network 0 {
Layer CONV {
Type: CONV
Dimensions { K: 64, C: 3, Y: 224, X: 224, R: 7, S: 7 }
Dataflow {
TemporalMap(200,200) Y';
TemporalMap(3,3) C;
TemporalMap(61,61) K;
TemporalMap(4,4) R;
SpatialMap(16,16) X';
TemporalMap(3,3) S;
Cluster(81,P);
TemporalMap(1,1) R;
TemporalMap(1,1) K;
TemporalMap(1,1) X';
TemporalMap(2,2) C;
SpatialMap(1,1) Y';
TemporalMap(1,1) S;
}
}
}