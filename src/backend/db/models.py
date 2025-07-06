from src.backend.db.methods import map_concepts, unmap_concepts


class StandardConcept:
    def __init__(
        self,
        concept_id: int,
        concept_name: str,
        domain_id: str,
        vocabulary_id: str,
        concept_class_id: str,
        standard_concept: str,
        concept_code: str,
    ):
        self.concept_id = concept_id
        self.concept_name = concept_name
        self.domain_id = domain_id
        self.vocabulary_id = vocabulary_id
        self.concept_class_id = concept_class_id
        self.standard_concept = standard_concept
        self.concept_code = concept_code


class SourceConcept:
    def __init__(
        self,
        source_id: int,
        source_value: str,
        source_concept_name: str,
        source_vocabulary_id: int,
        freq: int = 1,
        mapped: bool = False,
    ):
        self.source_id = source_id
        self.source_value = source_value
        self.source_concept_name = source_concept_name
        self.source_vocabulary_id = source_vocabulary_id
        self.freq = freq
        self.mapped = mapped

    def map_to_standard(self, standard_concepts: list[StandardConcept]):
        """Map this source concept to one or more standard concepts"""
        mappings = []
        for concept in standard_concepts:
            mappings.append(
                {"source_id": self.source_id, "concept_id": concept.concept_id}
            )

        map_concepts(mappings)
        self.mapped = True

    def unmap(self):
        """Remove all mappings for this source concept"""
        unmap_concepts([self.source_id])
        self.mapped = False


class DrugConcept(SourceConcept):
    def __init__(
        self,
        source_id: int,
        source_value: str,
        source_concept_name: str,
        source_vocabulary_id: int,
        atc_code: str = None,
        freq: int = 1,
        mapped: bool = False,
    ):
        super().__init__(
            source_id,
            source_value,
            source_concept_name,
            source_vocabulary_id,
            freq,
            mapped,
        )
        self.atc_code = atc_code
        self.drug_name = source_concept_name
        if atc_code:
            self.atc7 = atc_code[:7] if len(atc_code) >= 7 else atc_code
        else:
            self.atc7 = None
