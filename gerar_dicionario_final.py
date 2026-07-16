"""
gerar_dicionario_final.py
Gera o dicionario_base.json definitivo a partir do texto limpo do PDF.
"""
import json
import re

# Texto completo extraído do PDF (limpo e estruturado)
TEXTO_DICIONARIO = """
1ª Instância
Corresponde às Varas/Juizados Especiais, compostos por Juízes, e com atribuição para julgar os processos iniciados pelos cidadãos/empresas. É a principal porta de entrada do Poder Judiciário.
2ª Instância
Corresponde aos Órgãos Julgadores, compostos por Desembargadores, e com atribuição para julgar os recursos relativos às decisões judiciais da 1ª instância, além de outros tipos de ação.
2ª Vice-Presidência
Autua e distribui os processos de 2ª instância de matéria criminal, faz juízo de admissibilidade dos recursos constitucionais criminais e envia aos Tribunais Superiores.
3ª Vice-Presidência
Faz juízo de admissibilidade dos recursos constitucionais cíveis e envia aos Tribunais Superiores.
A quo
A instância de origem onde foi dada a decisão da qual se pretende recorrer. / Data inicial da contagem de um prazo.
Absolvição
Reconhecimento da inocência de uma pessoa.
Ação Judicial
É o meio processual para a defesa de um direito, levando o caso ao Poder Judiciário.
Ação Penal Privada
Ação judicial para apurar a prática de um crime e buscar a consequente aplicação da lei penal ao caso, que somente pode ser proposta pela própria vítima ou seu representante legal (exemplos: calúnia; difamação e injúria).
Ação Penal Pública
Ação judicial para apurar a prática de um crime e buscar a consequente aplicação da lei penal ao caso, que somente pode ser proposta pelo Ministério Público ou outro órgão público (exemplos: homicídio; estupro; roubo; furto e estelionato).
Ação Rescisória
Ação judicial que busca anular uma sentença ou acórdão já transitado em julgado.
Acórdão
Decisão final tomada por um colegiado de, no mínimo, 3 Desembargadores.
Ad cautelam
Por precaução.
Ad hoc
Pessoa com designação para uma determinada finalidade.
Ad quem
A instância superior a quem se recorre de uma sentença/decisão para que seja reavaliada. / Data final da contagem de um prazo.
Aditar
Acrescentar.
Advogado
Profissional formado em Direito que defende os interesses de quem o contratou.
Advogado Dativo
Advogado que se cadastra voluntariamente junto ao TJRJ para ser eventualmente nomeado para a defesa gratuita da parte que não poderia pagar pelos serviços de um advogado. O Advogado Dativo atua nas situações em que a Defensoria Pública não pode estar presente.
Agravado
Parte contrária àquela que apresenta o agravo.
Agravante
Parte que apresenta o agravo.
Agravo de Instrumento
Recurso apresentado ao Desembargador contra uma decisão interlocutória dada por um Juiz em um processo que está em andamento na 1ª instância.
Agravo em Recurso Especial
Recurso direcionado ao STJ contra decisão da 2ª ou 3ª Vice-Presidências que inadmitiu o Recurso Especial.
Agravo em Recurso Extraordinário
Recurso direcionado ao STF contra decisão da 2ª ou 3ª Vice-Presidências que inadmitiu o Recurso Extraordinário.
Agravo Interno
Recurso que busca a revisão da decisão monocrática dada pelo Desembargador Relator, submetendo-a ao colegiado. Utilizado nos casos previstos no Código de Processo Civil.
Agravo Regimental
Recurso que busca a revisão da decisão monocrática dada pelo Desembargador Relator, submetendo-a ao colegiado. Utilizado nos casos previstos no Regimento Interno do Tribunal.
Aguardando
Processo que se encontra na unidade judicial aguardando alguma providência, após o que, voltará a ser movimentado pelo funcionário.
Aguardando Decurso de Prazo - XX Dias
Processo que se encontra na unidade judicial aguardando o fim do prazo de XX dias, após o que, voltará a ser movimentado pelo funcionário.
Aguardando Julgamento no OE / STJ / STF
Processo que se encontra suspenso na unidade judicial, aguardando o julgamento de uma ação/recurso pelo Órgão Especial, STJ ou STF, após o que, ele voltará a ser movimentado pelo funcionário.
Aguardando Trânsito em Julgado
Processo já julgado que se encontra na unidade judicial, aguardando o fim do prazo que as partes dispõem para recorrer da decisão final.
Alvará de Soltura
Documento que determina a liberdade de uma pessoa que se encontra presa.
Amicus Curiae
'Amigo da corte'. Pessoa ou organização que não é parte em um caso, mas que o tribunal permite oferecer informações, conhecimentos ou perspectivas relevantes sobre as questões em discussão.
Anulação
Ato de invalidar uma decisão anterior, tornando-a sem efeito.
Apelação
Recurso apresentado para tentar mudar o resultado do julgamento.
Apelado
Parte contrária àquela que apresenta a apelação.
Apelante
Parte que apresenta a apelação.
Apensamento
Ato de vincular um processo a outro, para que passem a andar juntos.
Apud
Citado por. Conforme determinada fonte.
Ata de Audiência
Documento que registra as manifestações das partes, as decisões do juiz e quem estava presente.
Ata de Julgamento
Documento que registra os resultados dos julgamentos de todos os processos de uma mesma sessão de julgamento.
Ato Ordinatório
Publicação sem conteúdo decisório que serve para movimentar o processo.
Ato Processual
Ação/manifestação praticada pelas partes, Magistrado ou auxiliares da justiça, que objetiva produzir algum efeito no processo judicial, tais como petições, recursos, intimações e decisões.
Audiência de Conciliação
Realizada entre o autor e o réu, intermediada pelo conciliador (pessoa auxiliar da justiça), em que se busca chegar a um acordo entre as partes. Nela, o conciliador esclarece sobre as vantagens da conciliação e os riscos e consequências do litígio. Conseguida a conciliação, os termos do acordo são levados ao Magistrado para homologação.
Audiência de Custódia
Realizada com a pessoa que foi presa em flagrante, sendo apresentada a um Juiz que irá verificar a ocorrência de maus-tratos, bem como a legalidade da prisão e sua eventual conversão em prisão preventiva ou concessão de liberdade provisória. Durante a audiência também estarão presentes o Ministério Público e a Defensoria Pública ou advogado do preso.
Audiência de Instrução e Julgamento – AIJ
Realizada entre o autor, o réu e o Juiz, caso não tenha sido feito um acordo. Nela, o Juiz irá ouvir as partes, recolher as provas e decidir sobre o conflito.
Autor
Parte responsável por levar uma questão à apreciação do judiciário. Quem inicia o processo.
Autos do Processo
Conjunto dos documentos (eletrônicos ou em papel) produzidos pelas partes e pelo judiciário durante a ação judicial.
Autuação
Conjunto de atos necessários para formar um novo processo, a partir da petição inicial. Tais como: cadastrar a nova ação no sistema de movimentação processual do Tribunal, registrando o tipo de ação, a classificação dos assuntos envolvidos no conflito, a identificação do nome das partes e advogados, e o número de processo recebido.
Aviso de Recebimento – AR
Documento elaborado pelos Correios que permite confirmar a entrega de um objeto ou carta ao destinatário.
Baixa à Origem
Ocorre quando o processo é enviado à unidade onde ele foi iniciado.
Baixa em Diligência
Ocorre quando o Magistrado determina o envio do processo à unidade onde ele foi iniciado para que se cumpra determinada providência.
Bis in Idem
Duas vezes o mesmo. Refere-se à repetição de uma decisão sobre um mesmo fato.
Bloqueio On-Line
Ordem judicial feita aos bancos, determinando a retenção de certo valor nas contas bancárias da parte devedora.
Boa-fé
Que age honestamente, com conduta leal.
Câmara
Possui atribuição para julgar, entre outros, os recursos relativos a decisões judiciais das Varas da 1ª instância. Composta por 5 Desembargadores. Podendo ser: Câmara de Direito Privado, Câmara de Direito Público, Câmara de Direito Empresarial ou Câmara Criminal.
Carta Precatória
Documento com solicitações ou informações para a comunicação externa entre unidades judiciárias de diferentes comarcas dentro do Estado do Rio de Janeiro ou de diferentes estados brasileiros.
Cartório Judicial
Unidade judicial de 1ª instância responsável por praticar os atos de processamento, dando cumprimento às determinações do Juiz.
Caso Fortuito
Ocorrência de fato natural extraordinário, que não se pode prever nem evitar (Ex.: enchente e deslizamento de terra).
Causa mortis
O que provocou a morte da pessoa.
Central de Mandados
Unidade que gerencia o cumprimento dos mandados judiciais do TJRJ, recebendo-os das unidades judiciais e distribuindo entre os Oficiais de Justiça.
Certidão
Documento que atesta determinado fato ou situação processual.
Certidão de Decurso de Prazo
Documento feito pela unidade judicial que certifica o término do prazo para a prática de determinado ato processual.
Certidão de Objeto e Pé
Documento feito pela unidade judicial, onde são descritos, de forma resumida, o teor da ação judicial e o momento processual em que ela se encontra. Informam-se, ainda, o nome do requerente da certidão, o número do processo e o nome das partes e advogados.
Citação
Ato processual de comunicar à parte, que está sendo processada judicialmente, para apresentar a sua defesa.
Citado
Aquele que recebe uma citação.
Codex
Código.
Código Civil – CC
É a Lei nº 10.406/2002. O conjunto das normas que regulamentam os direitos e deveres das pessoas no âmbito do direito privado, ou seja, são as regras de procedimento nas relações de natureza civil.
Código de Defesa do Consumidor – CDC
É a Lei nº 8.078/1990. O conjunto das normas que regulamentam a proteção e defesa do consumidor.
Código de Processo Civil – CPC
É a Lei nº 13.105/2015. O conjunto das normas que regulamentam os prazos, os recursos e a condução nos Tribunais dos processos judiciais de natureza civil.
Código de Processo Penal – CPP
É o Decreto-Lei nº 3.689/1941. O conjunto das normas que regulamentam os prazos, os recursos e a condução nos Tribunais dos processos judiciais de natureza penal, bem como os direitos dos presos.
Código Penal – CP
É o Decreto-Lei nº 2.848/1940. O conjunto das normas que determinam e regulamentam os atos considerados crimes, bem como definem as sanções correspondentes.
Colegiado
Grupo de Magistrados que compõem determinado Órgão Julgador.
Com Resolução do Mérito
Ocorre quando o julgamento da ação decide sobre seu mérito, ou seja, os pedidos feitos no processo são analisados pela decisão final.
Comarca
Subdivisão territorial da organização do Poder Judiciário. Delimita a região em que o Juiz de 1ª instância exerce suas atribuições, podendo abranger um ou mais municípios.
Competência
Abrangência do limite do magistrado para julgar um processo, podendo ser determinado por diversos critérios, tais como: o assunto; as partes envolvidas; e o lugar onde ocorreu o fato.
Conclusão
Ato de enviar o processo ao Magistrado para que ele possa avaliar a questão presente nos autos e tome a decisão cabível.
Conflito de Competência
Ocorre quando dois ou mais Magistrados se declaram com, ou sem, atribuição para julgar o processo.
Conselho da Magistratura
Reúne 10 Desembargadores e possui atribuições específicas, definidas pelo Regimento Interno, tais como exercer superior inspeção e manter a disciplina na Magistratura, determinando correições e sindicâncias.
Conselho Recursal
Reúne as Turmas Recursais e possui atribuições para julgar os recursos relativos a decisões judiciais dos Juizados Especiais Cível, Fazendário e Criminal.
Constituição Federal
Lei fundamental que traz as regras de organização do Estado Brasileiro e das instituições da República, bem como os direitos e deveres dos cidadãos.
Contestação
Documento pelo qual a parte ré se defende dos fatos apresentados pelo autor na petição inicial.
Contrafé
Cópia da petição inicial que é entregue à parte citada.
Contramandado
Documento que torna sem efeito o mandado de prisão anterior, determinando o retorno daquele mandado à unidade judicial.
Contrarrazões
Documento pelo qual a parte recorrida se defende das razões alegadas no recurso.
Culposo
Que foi praticado sem intenção.
Curatela
Instituto jurídico para proteção do maior de 18 anos que, por algum motivo de incapacidade jurídica (enfermidade mental ou psicológica que o impeça de manifestar sua vontade), é interditado (declarado incapaz pelo Magistrado através de decisão) e um curador é nomeado para proteger seus direitos e interesses, e administrar seus bens.
Custas Processuais
Valor devido pelas partes para iniciar o processo, bem como para realizar atos processuais durante o andamento da ação.
Dano Material
Prejuízo financeiro causado a uma pessoa, gerando uma diminuição do seu patrimônio econômico (dinheiro ou bens materiais).
Dano Moral
Prejuízo emocional causado a uma pessoa, violando sua honra e dignidade, e gerando abalo psicológico.
Data vênia
Com a devida permissão.
Decadência
Perda do direito ocorrida quando seu titular deixa de agir dentro do prazo legal para seu exercício.
Decisão Interlocutória
Manifestação do Magistrado sobre uma questão incidental durante o andamento do processo, sem, contudo, encerrá-lo com o julgamento.
Decisão Judicial
Manifestação do Magistrado, feita no processo, que contém uma determinação.
Decisão Monocrática
Decisão de um único Magistrado.
Declínio de Competência
Ocorre quando o Magistrado envia o processo para distribuição a outro Juízo, que ele entende ser o competente para julgar o processo.
Defensoria Pública
Órgão público que presta atendimento jurídico de forma gratuita a pessoas que não teriam condições de pagar pelos serviços de um advogado.
Deferir
Atender a um pedido. Decisão favorável a quem pediu.
Denegar
Negar um pedido. Decisão desfavorável a quem pediu.
Denúncia
Petição inicial da ação penal pública, feita pelo Ministério Público para pedir a condenação de uma pessoa por fato criminoso.
Denúncia do Contrato
Manifestação de vontade da parte de não permanecer no contrato, visando a seu encerramento.
Depositário Infiel
Pessoa responsável pela guarda de um bem que não lhe pertence, e que não o devolve ao seu proprietário no momento devido.
Deprecado
Unidade que recebe uma Carta Precatória de outra unidade, contendo solicitações ou informações.
Deprecante
Unidade que envia uma Carta Precatória a outra unidade, encaminhando solicitações ou informações.
Desbloqueio
Ordem judicial para o banco liberar ao titular da conta o valor anteriormente retido.
Desembargador
Magistrado que atua na 2ª instância do Tribunal de Justiça.
Desembargador Relator
Desembargador para quem foi distribuído um processo, sendo ele o responsável por seu andamento até o julgamento. Cabe a ele fazer o relatório do processo e dar seu voto, que será levado aos demais Desembargadores do colegiado na sessão de julgamento.
Desembargador Revisor
Desembargador que revisa o processo, depois de o Relator apresentar seu relatório.
Desembargador Vogal
Desembargador que vota no julgamento de um processo, após o Desembargador Relator e, quando houver, o Desembargador revisor.
Deserção
Refere-se ao não pagamento das custas processuais do recurso, impossibilitando seu processamento.
Despacho
Manifestação do Magistrado com as medidas necessárias para o andamento do processo.
Detenção
Espécie de pena privativa de liberdade, que deve ser cumprida em regime semiaberto ou aberto, menos rigorosa que a pena de reclusão.
Devolução do Prazo
Ocorre quando o prazo para a prática de um ato processual já havia se encerrado, porém, ele é reiniciado por determinação do Magistrado.
Diário da Justiça Eletrônico (DJE/ DJERJ)
Meio oficial em que o TJRJ divulga seus atos processuais e administrativos, bem como comunicações em geral. É publicado eletronicamente, sendo acessado através de link disponível no site do Tribunal de Justiça.
Digitação
Processo que se encontra na fila da unidade judicial para a confecção de um documento, como mandado ou alvará, por exemplo.
Digitalização
Ato de digitalizar e transformar o processo físico em processo eletrônico.
Dilação de Prazo
Prorrogação do prazo previamente fixado para a prática de um ato processual.
Diligência
Providência determinada pelo Magistrado.
Direito Líquido e Certo
Direito da pessoa que não depende de interpretação ou análise e que pode ser comprovado de forma clara e objetiva, exclusivamente por documentos, sem a necessidade de provas adicionais.
Distribuição
Ato de definir o Magistrado que será o responsável por analisar e julgar o processo.
Doloso/ Dolo
Que foi praticado intencionalmente.
Duplo Grau de Jurisdição
Garantia da possibilidade de revisão de qualquer decisão proferida, por uma instância superior.
Edital de Citação
Documento que divulga e dá publicidade ao réu de que ele está sendo convocado a se apresentar no local indicado para fazer sua defesa no processo. Ocorre nos casos em que não se consegue localizar o réu.
Edital de Leilão
Documento que divulga e dá publicidade ao bem que será leiloado, trazendo as informações necessárias, como sua descrição e valor, e a data, o local e as regras e condições do leilão.
Edital-Pauta
Documento que traz a relação dos processos que serão levados à sessão de julgamento em determinado dia.
Efeito Suspensivo
Medida que suspende o cumprimento de uma decisão judicial até que ocorra o julgamento final de um recurso.
Em Mesa
Indica que o Desembargador irá levar o processo para julgamento em sessão de julgamento, não havendo, contudo, necessidade de incluí-lo no Edital-Pauta. Assim, não haverá necessidade de prévia intimação das partes sobre a data e horário em que ele será julgado.
Em Pauta
Indica que o processo será levado a julgamento, com a respectiva publicação da data e horário da sessão de julgamento através do Edital-Pauta.
Embargos de Declaração
Recurso dirigido ao próprio Magistrado que realizou o julgamento, para que ele esclareça alguma obscuridade, omissão ou contradição na decisão.
Ementa
Relatório bastante resumido do processo.
Escritura Pública
Documento feito no Cartório de Notas para registrar a vontade das partes envolvidas em um negócio.
Espólio
Relação dos bens, rendimentos, obrigações e direitos que compõem o patrimônio do falecido.
Ex lege
De acordo com a lei.
Ex nunc
Com efeitos que operam a partir do momento presente; a contar da data de uma decisão em diante.
Ex positis
Do que ficou estabelecido.
Ex tunc
Com efeitos que operam desde um momento passado, anterior à data de uma decisão, em diante. A contar desde o início da ocorrência de um fato passado.
Ex vi legis
Por força de lei.
Executado Judicial
Aquele que está sendo cobrado a cumprir uma condenação judicial.
Expedição de Documento
Ato de elaborar um mandado ou alvará, por exemplo, e remetê-lo ao destinatário.
Expediente Forense
Refere-se aos dias, ou ao horário, em que as atividades jurisdicionais e administrativas do Tribunal estão em funcionamento.
Extra petita
Algo diferente do pedido feito pela parte.
Flagrante Delito
Ocorre quando uma pessoa é surpreendida cometendo um crime ou tendo acabado de cometê-lo.
Força Maior
Situação decorrente da ação humana, que não se pode prever nem evitar (Ex.: guerra e greve.)
Fulcro
Baseado em/ Aquilo que constitui a essência de uma coisa.
Fumus Boni Iuris
'Fumaça do bom direito'. Significa que a alegação feita é plausível.
Fundamentação
Parte da decisão em que o Magistrado expõe as razões pelas quais formou seu convencimento sobre o caso.
Gabinete
Local onde o Magistrado despacha e desenvolve suas atividades.
Gratuidade de Justiça (JG)
Isenção das custas processuais concedida à parte que não tem condições financeiras de pagá-las.
GRERJ
Sigla para Guia de Recolhimento de Receita Judiciária, e serve para o pagamento das custas processuais devidas ao TJRJ por uma das partes.
Grupo de Câmara Criminal
Reúne 10 Desembargadores das Câmaras Criminais e possui atribuições específicas, definidas pelo Regimento Interno.
Habeas Corpus
Ação judicial que serve para proteger a liberdade de locomoção (ir e vir) de uma pessoa, quando esse direito é ameaçado ou violado por ato ilegal ou abuso de poder de uma autoridade pública.
Habeas Data
Ação judicial que serve para garantir o acesso de uma pessoa a dados e informações sobre ela mesma que constam nos registros públicos.
Habilitação
Quando o herdeiro/sucessor pede à Justiça para assumir o lugar do falecido no processo.
Hipossuficiência
Que não possui recursos para se sustentar financeiramente.
Homologação de Acordo
Ocorre quando o acordo feito entre as partes do processo é confirmado pelo Magistrado através de uma decisão, podendo ser executado judicialmente em caso de não cumprimento.
Honorários Advocatícios
Remuneração devida ao advogado, pelos serviços por ele prestados, a ser pago pelo cliente que o contratou, independentemente do resultado do processo.
Honorários de Sucumbência
Valor fixado por lei a ser pago, pela parte perdedora do processo, ao advogado da parte vencedora.
Impedimento do Magistrado
Ocorre quando o Magistrado não pode ser o responsável pelo processo que lhe foi distribuído (art. 144 do CPC).
Improcedência do Pedido
Ocorre quando o Magistrado não aceita o pedido feito pela parte.
Impugnar
Refutar. Opor-se a algo.
In albis
Em branco. Ausência de manifestação da parte interessada.
In fine
Finalmente. 'No final'.
In totum
Em sua totalidade. 'No todo'.
Inadimplência
Não cumprimento de um contrato. Não pagamento da dívida no dia de seu vencimento.
Inelegibilidade
Condição de uma pessoa que não pode se candidatar a um cargo político ou ser eleita para um mandato eletivo.
Inimputável
Aquele que, por doença mental ou desenvolvimento mental incompleto ou retardado (art. 26 do Código Penal), é inteiramente incapaz de entender o caráter ilícito de sua ação ou da omissão, e, por isso, é isento de pena.
Inquérito Policial
Procedimento administrativo realizado pela polícia judiciária (Polícias Civil e Federal) em que são reunidas as informações do caso e diligências realizadas, a fim de apurar a existência de infração penal e sua autoria, embasando possível ação penal posterior.
Instância Superior
Responsável por apreciar os recursos relativos as decisões judiciais do Juízo em que o processo atualmente se encontra.
Intempestivo
Ato processual feito após o prazo estabelecido pela lei ou pelo Magistrado.
Interpretação Pacífica
Entendimento adotado pela maioria do Tribunal a respeito de determinado caso/situação.
Intimação
Comunicação destinada aos advogados e partes, dando-lhes ciência de alguma decisão ou da prática de um ato no processo. Pode ser realizada através do envio de um documento físico ou eletrônico à parte que se deseja intimar.
Intimação Eletrônica
Envio de comunicação processual por mensagem eletrônica.
Inventário
Ação para levantar os bens deixados pelo falecido e distribuir entre os herdeiros.
Ipsis litteris
Literalmente. 'Com as mesmas letras'.
Ipso facto
Pelo mesmo fato.
Juiz
Aquele que tem a atribuição, dada pelo Estado, de aplicar a lei aos casos que lhe são trazidos e julgá-los, resolvendo o conflito entre as partes na 1ª instância.
Juiz Leigo
Auxiliar da justiça formado em Direito, escolhido pelo TJRJ através de processo seletivo para atuação por determinado período, que tem a atribuição de elaborar projetos de sentença, a serem submetidos ao Juiz, que poderá concordar ou dar outra sentença.
Juizado Especial (Cível, Fazendário e Criminal)
Órgão com atribuição para julgar os processos de menor complexidade e valor, pelo rito célere da Lei nº 9.099/95 (Juizado Especial Cível e Criminal) ou da Lei nº 12.153/09 (Juizado Especial Fazendário).
Juízo 100% Digital
Modo de tramitação totalmente digital do processo, em que o processamento e o julgamento são realizados de forma remota (dispensando a presença física das partes), em ambiente virtual.
Juízo de Admissibilidade
Exame feito pela 2ª ou 3ª Vice-Presidências para analisar se os Recursos Extraordinário, Especial ou Ordinário Constitucional reúnem os requisitos necessários para serem remetidos ao STF ou STJ.
Julgamento
Ato que decide sobre o processo e, nele, o Magistrado relata e fundamenta as razões que o levaram àquele entendimento.
Julgamento Monocrático
Ocorre quando apenas um Desembargador julga o processo, sem levar o caso à sessão de julgamento, para análise pelos demais Desembargadores da Câmara.
Juntada
Ato de juntar um documento novo no processo.
Jurisprudência
Conjunto de decisões dadas pelo Tribunal que possuem uma mesma interpretação sobre o mesmo caso.
Lato sensu
Em sentido geral.
Leiloeiro
A pessoa que realiza o leilão.
Licitação
Processo administrativo pelo qual a Administração Pública contrata obras, serviços, compras e alienações.
Litígio
Ação. Disputa judicial entre autor e réu, estabelecida após a apresentação da contestação.
Má-fé
Com a intenção de causar prejuízo. Que altera a verdade dos fatos.
Magistrado
Sinônimo de Juiz ou Desembargador.
Malote Digital
Sistema eletrônico utilizado para o envio de correspondências oficiais entre os Órgãos do Poder Judiciário de todo o Brasil.
Mandado
Documento que traz escrita a ordem dada pelo Magistrado, a ser cumprida.
Mandado de Busca e Apreensão
Documento com ordem para que se apreenda uma coisa/pessoa, em poder de outra pessoa, em determinado local.
Mandado de Citação
Documento informando ao réu sobre a existência de uma ação contra ele e convocando-o a apresentar sua defesa no processo.
Mandado de Pagamento
Documento determinando ao banco (conveniado ao Tribunal) entregar a quantia depositada em conta judicial a determinada pessoa.
Mandado de Prisão
Documento determinando a prisão de uma pessoa.
Mandado de Segurança
Ação judicial que serve para proteger direito líquido e certo (ou seja, direito incontestável que pode ser provado exclusivamente por documentos) que tenha sido ameaçado ou violado por ato ilegal ou abuso de poder de uma autoridade pública.
Mandato
Sinônimo de procuração.
Medida Socioeducativa
Sanção judicial aplicada ao adolescente que comete ato infracional.
Memorando
Documento com solicitações ou informações para a comunicação interna entre unidades/órgãos do TJRJ.
Memoriais
Documento feito pelo advogado a fim destacar ou esclarecer, ao Magistrado, questões complexas presentes no processo, antes de seu julgamento.
Mens legis
O espírito da lei. A intenção da lei.
Ministério Público
Órgão público responsável por defender na Justiça os interesses da sociedade e do regime democrático.
Minuta
Esboço de um documento a ser submetido à avaliação.
Modus operandi
O modo de operar/ modo de agir.
Mora
Atraso no cumprimento de uma obrigação.
Mora ex re
Mora devida pelo não cumprimento de uma obrigação no dia do seu vencimento.
Negativação
Inscrição do nome da pessoa nos cadastros de proteção ao crédito (como o Serasa e SPC).
Oficial de Justiça
Servidor do Tribunal que tem a atribuição de dar cumprimento à determinação contida nos mandados e alvarás, realizando citações, intimações, prisões, solturas, penhoras, busca e apreensão e demais diligências.
Ofício
Documento para comunicação externa de unidades/órgãos do TJRJ com destinatários que não integram a estrutura do TJRJ.
Ônus
Obrigação a ser cumprida.
Ônus da prova
Obrigação de comprovar as alegações feitas no processo, através de documentos ou testemunhas.
Ordem dos Advogados do Brasil – OAB
Órgão responsável por registrar e fiscalizar os advogados.
Órgão Especial do TJRJ
Reúne 25 Desembargadores e possui atribuições específicas, definidas pelo Regimento Interno, tais como julgar, originariamente, o Vice-Governador, os Deputados Estaduais e os Secretários de Estado nos crimes; julgar os Habeas Corpus quando a autoridade coatora for o Governador do Estado; e julgar os dissídios coletivos e estado de greve.
Órgão Julgador
Órgão colegiado (ou seja, formado por um grupo de Magistrados) que compõe o Tribunal, como, por exemplo, as Câmaras, as Seções Cíveis, os Grupos de Câmara Criminal, o Órgão Especial, o Tribunal Pleno e o Conselho da Magistratura.
Ouvidoria
Recebe sugestões, perguntas ou reclamações sobre as atividades do TJRJ.
Para Processar
Processo que se encontra na fila da unidade judicial para análise pelo funcionário que dará seu devido andamento, seja juntando uma petição, expedindo uma certidão, enviando os autos ao Magistrado, ou, ainda, dando cumprimento ao determinado na decisão.
Para Publicar
Processo que se encontra na fila da unidade judicial para que o despacho/decisão, dado pelo Magistrado, seja enviado ao Diário da Justiça Eletrônico e ali publicado.
Parecer do Ministério Público
Manifestação do Ministério Público no processo com sua opinião sobre o caso e os pedidos.
Parecer Técnico
Documento que traz as avaliações e conclusões do perito sobre o caso por ele analisado.
Pari passu
Simultaneamente. 'Com o mesmo passo'.
Parte
Pessoa (física ou jurídica) que participa do processo, como, por exemplo, o autor e o réu.
Partilha
Distribuição dos bens do falecido entre os herdeiros.
Patrono
Advogado ou Defensor Público que defende os interesses da parte no processo.
Pauta de Julgamento
Lista que contém a relação dos processos que serão julgados na sessão de julgamento indicada, em dia e hora determinados.
Peculato
Crime em que o funcionário público se apropria de dinheiro ou qualquer bem móvel de que tem a posse em razão do cargo.
Pedido de Liminar
Pedido feito pela parte para que o Magistrado lhe conceda um direito antecipadamente, ainda que de forma provisória e antes mesmo do julgamento final do processo, por alegada urgência e risco de perda do direito em caso de demora em seu reconhecimento definitivo.
Pedindo Dia
Indica a determinação para que o processo seja incluído em uma sessão de julgamento.
Pedindo Dia - Sessão Virtual
Indica a determinação para que o processo seja incluído em uma sessão de julgamento virtual.
Pena
Sinônimo de condenação que o réu terá que cumprir.
Penhora
Instrumento judicial para reter os bens do devedor (restringindo os direitos de propriedade, como a venda, por exemplo), a fim de garantir que eles possam ser usados posteriormente para o pagamento da dívida.
Perícia
Avaliação realizada pelo perito.
Perito
Profissional com especialização e experiência em determinada área da ciência, que auxilia o Magistrado dando parecer técnico sobre uma questão discutida no processo.
Petição
Pedido feito por escrito.
Petição Inicial
Relato inicial do autor, em que ele narra os acontecimentos que pretende levar à apreciação do judiciário, e também faz os pedidos que deseja obter. Documento com o qual se inicia um processo.
Pleitear
Pedir. Requerer.
Poder Judiciário
É um dos poderes do Estado que possui a atribuição de julgar conflitos e aplicar as leis.
Poderes da Procuração
São as autorizações, e seus limites que constam na procuração para poder agir em nome de outra pessoa.
Precatório Judicial
Determinação judicial feita à Fazenda Pública para que ela pague determinada quantia a seu credor, em razão de condenação final do ente público em um processo.
Precedente
Decisões judiciais que podem servir como exemplos para outros julgamentos em casos semelhantes.
Preclusão
Perda do direito de praticar um ato processual, seja pela parte não ter agido dentro do prazo legal para seu exercício, seja por já o ter praticado.
Preparo
Refere-se ao pagamento das custas processuais para o processamento do recurso.
Prescrição
Perda do direito de interpor uma ação, quando seu titular deixa de agir dentro do prazo legal para seu exercício.
Prevenção
Ocorre quando, no momento da distribuição por sorteio, dentre os vários Magistrados aptos a serem os responsáveis pelo julgamento do processo, um deles, por algum motivo, tem a preferência legal para ser o seu responsável/relator.
Prima facie
À primeira vista.
Prisão em Flagrante
Ocorre quando a pessoa é presa em flagrante delito (cometendo um crime ou logo após cometê-lo).
Pro forma
Por mera formalidade.
Procedência do Pedido
Ocorre quando o Magistrado aceita o pedido feito pela parte.
Processo Eletrônico
Processo que é formado por documentos ('peças') eletrônicos. Ou seja, suas peças não são impressas em papel e o processo somente pode ser consultado através de um dispositivo eletrônico, como computador, tablet ou celular.
Processos Baixados em Diligência
Processo enviado à Vara de origem para alguma providência e que voltará para a 2ª Instancia.
Procuração
Documento em que a pessoa concede poderes a um advogado para representá-la perante a Justiça, autorizando-o a praticar atos jurídicos em seu nome.
Procuradoria Geral do Estado
Órgão responsável por defender na Justiça os interesses do Estado do Rio de Janeiro.
Procuradoria Geral do Município
Órgão responsável por defender na Justiça os interesses do Município.
Progressão de Regime
Direito do preso de passar a cumprir sua pena com regras menos rigorosas, caso preencha os requisitos previstos em lei.
Projeto de Sentença
Parecer jurídico elaborado pelo Juiz Leigo, com sua avaliação sobre o julgamento do caso, que é imediatamente submetido ao Juiz, que poderá concordar ou dar nova sentença.
Promotor
Aquele que trabalha no Ministério Público e que tem como atribuição a defesa dos interesses da sociedade.
Protesto
Ato de registrar, no Cartório de Protesto de Títulos, a dívida não paga no prazo definido.
Protocolo
Recibo composto por uma sequência de números que comprova que o documento foi entregue ao Tribunal.
Publicação
Ocorre quando uma comunicação judicial é tornada pública através de sua divulgação no Diário da Justiça Eletrônico.
Publicados
Processo cuja decisão já foi publicada no Diário da Justiça Eletrônico, e que se encontra na fila da unidade judicial para certificação desse fato e devido andamento.
Queixa-Crime
Petição inicial da ação penal privada, em que a exposição do fato criminoso e a respectiva acusação são feitas pela própria vítima (ou seu representante).
Querelado
Parte acusada contra a qual foi oferecida a Queixa-Crime.
Querelante
Parte acusadora que leva a Queixa-Crime à Justiça.
Questão Constitucional
Assunto que envolve a interpretação de normas da Constituição Federal do Brasil.
Quórum
Número mínimo necessário de Desembargadores presentes em plenário para o prosseguimento da sessão de julgamento e realização do julgamento.
Recesso do Judiciário
Suspensão do expediente forense entre 20 de dezembro e 6 de janeiro, período em que também ocorre a suspensão legal dos prazos processuais (que se encerra em 20 de janeiro, conforme art. 220 do CPC).
Reclusão
Prisão com isolamento (regime fechado).
Recorrente
Parte que apresenta o recurso.
Recorrido
Parte contrária àquela que apresenta o recurso.
Recurso
Utilizado para a impugnar uma decisão judicial, buscando sua revisão total ou parcial.
Recurso Especial
Recurso dirigido ao STJ. Contudo, antes de seu envio ao STJ é realizado o 'juízo de admissibilidade' pela 2ª ou 3ª Vice-Presidências para analisar se o recurso reúne os requisitos necessários para ser remetido àquela instância superior.
Recurso Extraordinário
Recurso dirigido ao STF. Contudo, antes de seu envio ao STF é realizado o 'juízo de admissibilidade' pela 2ª ou 3ª Vice-Presidências para analisar se o recurso reúne os requisitos necessários para ser remetido àquela instância superior.
Recurso Inominado
Recurso apresentado às Turmas Recursais (composta por Juízes) pela parte insatisfeita com a sentença, dada por outro Juiz na 1ª instância (nos Juizados Especiais Cível, Fazendário ou Criminal), a fim de alterar o resultado do julgamento.
Recurso Ordinário Constitucional
Recurso dirigido ao STF ou STJ. Contudo, antes de seu envio ao STF ou STJ é realizado o 'juízo de admissibilidade' pela 2ª ou 3ª Vice-Presidências para analisar se o recurso reúne os requisitos necessários para ser remetido àquelas instâncias superiores.
Recurso Repetitivo
Trata-se de um sistema de padronização de decisões, para garantir que Recursos Especiais que tratem da mesma questão jurídica sejam julgados, pelos tribunais brasileiros, com a mesma interpretação pacífica (chamada 'tema') dada pelo STJ.
Redistribuição
Ocorre quando um novo Juiz/Desembargador passa a ser o responsável/relator do processo, substituindo o antigo.
Regimento Interno do TJRJ
Conjunto de normas que regulamenta o funcionamento dos Órgãos do TJRJ.
Registro Geral de Imóveis – RGI
Refere-se tanto ao documento que formaliza e oficializa a transferência de um imóvel entre pessoas quanto ao Cartório onde se realizam e ficam armazenados os registros.
Relatório
Texto que narra detalhadamente os fatos, eventos e manifestações que fazem parte do processo.
Remessa
Envio. Encaminhamento.
Renúncia de Mandato
Ocorre quando o advogado comunica à pessoa que o contratou que abre mão dos poderes da procuração que lhe foram conferidos, não tendo mais interesse em representa-lo (continuar no processo).
Repercussão Geral
Trata-se de um sistema de padronização de decisões, para garantir que Recursos Extraordinários que tratem da mesma questão constitucional sejam julgados, pelos tribunais brasileiros, de acordo com a interpretação pacífica (chamada 'tema') dada pelo STF.
Réplica
Resposta do autor às alegações trazidas pelo réu em sua contestação.
Representante Legal
Aquele que tem autoridade, dada pela lei, para agir em nome de outra pessoa.
Requerimento
Pedido feito por escrito.
Retirada de Pauta
Ocorre quando o Magistrado determina a retirada de um processo da sessão de julgamento em que ele já estava para ser julgado.
Réu
Parte contra quem o autor demanda em um processo judicial.
Revelia
Ocorre quando um réu não atende à citação para se defender e deixa de apresentar contestação no processo.
Sanção
Medida punitiva ou educativa aplicada por um Magistrado.
Seções Cíveis
Dividem-se em Seção de Direito Privado e Seção de Direito Público.
Seção de Direito Privado
Reúne 15 Desembargadores das Câmaras de Direito Privado e possui atribuições específicas, definidas pelo Regimento Interno.
Seção de Direito Público
Reúne 7 Desembargadores das Câmaras de Direito Público e possui atribuições específicas, definidas pelo Regimento Interno.
Secretaria de Câmara
Unidade judicial de 2ª instância responsável por praticar os atos de processamento, dando cumprimento às determinações dos Desembargadores dos Órgãos Julgadores e zelando pelo regular andamento de uma ação judicial (acompanhando os prazos para manifestação das partes, realizando publicações e intimações, digitando e expedindo documentos e abrindo conclusão ao Magistrado, por exemplo).
Sem Resolução de Mérito
Ocorre quando a ação termina sem decidir sobre seu mérito, ou seja, os pedidos feitos no processo não são analisados na decisão final.
Sentença
Manifestação por escrito do Magistrado em que ele decide sobre o caso na 1ª instância.
Sessão de Julgamento
Reunião de Desembargadores de determinado Órgão Julgador para julgar os processos inclusos na pauta de julgamento.
Sobrestamento
Suspensão. Paralisação temporária do andamento do processo.
STF
Sigla para Supremo Tribunal Federal, que é o órgão máximo do Poder Judiciário brasileiro e a quem cabe a defesa e a interpretação da Constituição.
STJ
Sigla para Superior Tribunal de Justiça (conhecido como 'Tribunal da Cidadania'), que é a instância máxima da justiça brasileira na defesa e na interpretação das leis federais (em questões não relacionadas diretamente à Constituição).
Substabelecimento Com Reserva de Poderes
Documento pelo qual o advogado, que já possui procuração, transfere parte de seus poderes para o novo advogado, passando ambos a atuar conjuntamente na representação.
Substabelecimento Sem Reserva de Poderes
Documento pelo qual o advogado, que já possui procuração, transfere total e definitivamente seus poderes para o novo advogado (que irá assumir a causa).
Súmula
Registro das interpretações pacíficas ou majoritárias do Tribunal (jurisprudência).
Suspeição do Magistrado
Ocorre quando o Magistrado, por alguma razão subjetiva que pudesse vir a comprometer sua imparcialidade, não pode ser o responsável pelo processo que lhe foi distribuído (casos elencados no art. 145 do CPC).
Suspensão
Ocorre quando o Magistrado determina que o processo deixe de ser movimentado por algum período (ou seja, deixam de ser praticados atos processuais, exceto os de urgência). Assim, o processo permanece na unidade judicial aguardando a ocorrência do fato que porá fim à suspensão.
Tabelar
Substitui o titular em sua função, quando este não pode ou não deve atuar no caso.
Tempestivo
Ato processual feito dentro do prazo estabelecido pela lei ou pelo Magistrado.
Testemunha
Pessoa que não é parte do processo (ou seja, nem autor, nem réu), mas que tem conhecimento sobre o assunto que está sendo discutido. Por este motivo, é chamada para responder as perguntas do Juiz e das partes, devendo dizer apenas a verdade, sob pena de cometer crime de mentir em Juízo.
TJRJ
Sigla para Tribunal de Justiça do Estado do Rio de Janeiro.
Tramitação
Andamento dos atos processuais ocorridos no decorrer de um processo.
Trânsito em Julgado
Ocorre quando uma decisão (exemplo: sentença, julgamento monocrático ou acórdão) torna-se definitivo por não haver mais possibilidade de ser reavaliada.
Tribunais Superiores
Referem-se aos órgãos máximos do Poder Judiciário, tais como o STF e o STJ.
Tribunal Pleno
Órgão julgador composto por todos os Desembargadores do Tribunal de Justiça do Estado do Rio de Janeiro.
Turma Recursal
Subdivisão do Conselho Recursal. Órgão composto por 5 juízes de direito, com mandatos de dois anos, com atribuição para julgar os recursos oriundos dos Juizados Especiais Cível, Fazendário e Criminal.
Ultra petita
Algo que ultrapassa o pedido feito pela parte.
Unidade Judicial
Sinônimo de Cartório Judicial ou de Secretaria de Câmara.
Vara
Repartição judiciária de 1ª instância em que o Juiz exerce suas atribuições. Compreende o Cartório, onde são realizadas as atividades de processamento, e o gabinete, onde o Juiz se ocupa da análise dos processos e das decisões.
Vara de Origem
Refere-se ao Juízo de 1ª instância que primeiro julgou o processo.
Virtualização
Ato de integrar os documentos digitalizados de um processo, então físico, aos sistemas de movimentação processual eletrônica do Tribunal.
Vista dos Autos
Recebimento do processo, pelo Magistrado, para análise.
Voto
Exposição dos fatos, razões e fundamentos que levaram o Desembargador a consolidar seu entendimento sobre como o processo deve ser julgado.
Voto Vencido
Voto dado pelo Desembargador que não acompanha o entendimento da maioria do colegiado (grupo) no julgamento de um processo.
Writ
Sinônimo de Habeas Corpus e Mandado de Segurança.
"""

def extrair_verbetes(texto):
    """Extrai verbetes do texto usando padrões de linha."""
    linhas = texto.strip().split('\n')
    verbetes = []
    
    i = 0
    while i < len(linhas):
        linha = linhas[i].strip()
        
        # Pula linhas vazias
        if not linha:
            i += 1
            continue
        
        # Verifica se é um título (linha curta que não termina com ponto)
        if len(linha) < 60 and not linha.endswith('.') and not linha.endswith(','):
            titulo = linha
            i += 1
            
            # Coleta definição
            definicao_partes = []
            while i < len(linhas):
                proxima = linhas[i].strip()
                if not proxima:
                    i += 1
                    continue
                # Se próxima linha for novo título, paramos
                if len(proxima) < 60 and not proxima.endswith('.') and not proxima.endswith(','):
                    break
                definicao_partes.append(proxima)
                i += 1
            
            definicao = " ".join(definicao_partes).strip()
            
            if len(definicao) > 10:
                verbetes.append({
                    "titulo": titulo,
                    "texto": definicao
                })
        else:
            i += 1
    
    return verbetes

if __name__ == "__main__":
    print("🔄 Gerando dicionario_base.json definitivo...")
    
    verbetes = extrair_verbetes(TEXTO_DICIONARIO)
    
    # Salva JSON
    with open("dicionario/dicionario_base.json", 'w', encoding='utf-8') as f:
        json.dump(verbetes, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Sucesso! {len(verbetes)} verbetes extraídos.")
    print(f"📁 Salvo em: dicionario/dicionario_base.json")
    
    # Validação
    print("\n🔍 Primeiros 5 verbetes:")
    for i, v in enumerate(verbetes[:5]):
        print(f"\n{i+1}. 📌 {v['titulo']}")
        print(f"   💬 {v['texto'][:100]}...")
    
    print("\n" + "="*60)
    print("✅ CONCLUÍDO")
    print("="*60)
    print("Próximo passo: python indexar_dicionario.py")
