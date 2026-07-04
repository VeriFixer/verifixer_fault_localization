Bugs to correct:
Method exam score is to lignint if method predicts something outside the method, ignoring the prdiciton only makes score better. Instead I should do other thing (at least increase the rank variable that is measuring that and clamp to one in the worse case)



Bug to correct on the reassume 
python src/evaluators/eval_1_model_1_example.py counterExampleIfReassume dataset/data/pos_test/killed/example_to_test_reassume_single_fault__MUTANT.dfy 







counterbasIf should have solved this as counterbase solved it

Sample counterBase-only successes:
  /app/datasets/dafnytestgen_tests_can_run/dafnytestgen_tests_can_run/killed/dafny-synthesis_task_id_447__238-240_EVR_int.dfy: counterBase score=0.0625, counterExampleIf score=0.5625



With latest changes this broke, need to debug 
counterExampleReasume should have this

Sample counterExampleIf-only successes:
  /app/datasets/dafnytestgen_tests_can_run/dafnytestgen_tests_can_run/killed/dafl_tmp_tmp_r3_8w3y_dafny_examples_uiowa_binary-search__689_ROR_Eq.dfy: counterExampleIf score=0.1000, counterExampleIfReassume score=0.5750
  /app/datasets/dafnytestgen_tests_can_run/dafnytestgen_tests_can_run/killed/dafny_examples_tmp_tmp8qotd4ez_leetcode_0069-sqrt__545_AOR_Sub.dfy: counterExampleIf score=0.0789, counterExampleIfReassume score=0.5658
  /app/datasets/dafnytestgen_tests_can_run/dafnytestgen_tests_can_run/killed/Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from dafny main repo_dafny2_COST-verif-comp-2011-3-TwoDuplicates__4966_VER_p.dfy: counterExampleIf score=0.1356, counterExampleIfReassume score=0.5763
  /app/datasets/dafnytestgen_tests_can_run/dafnytestgen_tests_can_run/killed/pucrs-metodos-formais-t1_tmp_tmp7gvq3cw4_fila__3518_VER_i.dfy: counterExampleIf score=0.0355, counterExampleIfReassume score=0.5000
